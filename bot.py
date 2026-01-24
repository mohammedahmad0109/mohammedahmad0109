import os
import json
import time
import asyncio
import shlex
import requests
from io import BytesIO
from requests.auth import HTTPBasicAuth

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ========= ENV =========

BOT_TOKEN = os.getenv("BOT_TOKEN")
VERIF_LOGIN = os.getenv("VERIF_LOGIN")
VERIF_PASSWORD = os.getenv("VERIF_PASSWORD")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not VERIF_LOGIN or not VERIF_PASSWORD:
    raise RuntimeError("VERIF_LOGIN / VERIF_PASSWORD not set")

# ========= API CONFIG =========

API_BASE = "https://backend.com.de/api/integration"
AUTH = HTTPBasicAuth(VERIF_LOGIN, VERIF_PASSWORD)

session = requests.Session()
session.auth = AUTH
session.headers.update({
    "User-Agent": "telegram-generator-bot",
    "Accept": "application/json",
})

# ========= MEMORY =========

user_images = {}  # user_id -> BytesIO

# ========= HELPERS =========

def parse_kv_args(text: str) -> dict:
    args = shlex.split(text)
    data = {}

    for arg in args:
        if "=" not in arg:
            raise ValueError(f"Invalid argument: {arg}")
        k, v = arg.split("=", 1)
        data[k.upper()] = v

    return data


def download_image(url: str) -> BytesIO:
    r = session.get(url, timeout=30)
    r.raise_for_status()

    bio = BytesIO(r.content)
    bio.name = "result.jpg"
    bio.seek(0)
    return bio


def wait_until_task_exists(task_id: str, timeout=10):
    start = time.time()
    while True:
        r = session.get(
            f"{API_BASE}/generation-status/{task_id}/",
            timeout=10,
        )
        if r.status_code == 200:
            return
        if time.time() - start > timeout:
            return
        time.sleep(0.5)


def get_csrf_token() -> str:
    """
    Swagger does a GET first to obtain csrftoken cookie.
    We must do the same.
    """
    r = session.get(
        f"{API_BASE}/pay-for-result/",
        timeout=10,
    )
    r.raise_for_status()

    csrf = session.cookies.get("csrftoken")
    if not csrf:
        raise Exception("CSRF token not found in cookies")

    return csrf

# ========= GENERATOR 2 =========

def generate_task_gen2(data: dict, image_bytes: BytesIO | None):
    files = {
        "generator": (None, "uk_passport_new_fast"),
        "data": (
            None,
            json.dumps(data),
            "application/json",
        ),
    }

    if image_bytes:
        files["image1"] = ("input.jpg", image_bytes, "image/jpeg")

    r = session.post(
        f"{API_BASE}/generate/",
        files=files,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["task_id"]


def pay_for_result(task_id: str) -> str:
    csrf = get_csrf_token()

    headers = {
        "X-CSRFToken": csrf,
    }

    r = session.post(
        f"{API_BASE}/pay-for-result/",
        json={"task_id": task_id},
        headers=headers,
        timeout=30,
    )

    if r.status_code != 201:
        raise Exception(f"PAY ERROR {r.status_code}: {r.text}")

    image_url = r.json().get("image_url")
    if not image_url:
        raise Exception("Payment succeeded but no image_url returned")

    return image_url

# ========= TELEGRAM HANDLERS =========

async def handle_photo(update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    bio = BytesIO()
    await file.download_to_memory(bio)
    bio.name = "input.jpg"
    bio.seek(0)

    user_images[update.effective_user.id] = bio

    await update.message.reply_text(
        "📸 Image received.\n\n"
        "Please enter this command:\n\n"
        "fn=firstname ln=lastname dob=DD.MM.YYYY sex=M/F\n\n"
        "Example:\n"
        "/test2 fn=Jane ln=Dawson dob=\"12.12.1999\" sex=F"
    )


async def test2(update, context: ContextTypes.DEFAULT_TYPE):
    loop = asyncio.get_running_loop()
    user_id = update.effective_user.id

    try:
        if not context.args:
            await update.message.reply_text(
                "/test2 fn=firstname ln=lastname dob=\"DD.MM.YYYY\" sex=M/F"
            )
            return

        data = parse_kv_args(" ".join(context.args))
        image_bytes = user_images.get(user_id)

        await update.message.reply_text("💳 Generating & paying…")

        task_id = await loop.run_in_executor(
            None, lambda: generate_task_gen2(data, image_bytes)
        )

        await loop.run_in_executor(
            None, lambda: wait_until_task_exists(task_id)
        )

        image_url = await loop.run_in_executor(
            None, lambda: pay_for_result(task_id)
        )

        photo = await loop.run_in_executor(
            None, lambda: download_image(image_url)
        )

        await update.message.reply_photo(
            photo=photo,
            caption="✅ FINAL RESULT",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ ERROR:\n{e}")

# ========= APP =========

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("test2", test2))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

app.run_polling()