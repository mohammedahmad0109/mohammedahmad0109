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
session.headers.update({"User-Agent": "telegram-generator-bot"})

# ========= IN-MEMORY STORAGE =========

user_images = {}  # user_id -> BytesIO

# ========= HELPERS =========

def parse_kv_args(text: str) -> dict:
    """
    Parses:
    LN=DOE FN="JOHN LEE" DOB=123 SEX=M
    """
    args = shlex.split(text)
    data = {}

    for arg in args:
        if "=" not in arg:
            raise ValueError(f"Invalid argument: {arg}")

        key, value = arg.split("=", 1)
        data[key.upper()] = value

    return data


def download_image_to_memory(url: str) -> BytesIO:
    r = session.get(url, timeout=30)
    r.raise_for_status()

    bio = BytesIO(r.content)
    bio.name = "result.jpg"
    bio.seek(0)
    return bio

# ========= GENERATOR 1 (UNCHANGED) =========

def generate_task_gen1():
    r = session.post(
        f"{API_BASE}/generate/",
        files={
            "generator": (None, "bank_check"),
            "data": (
                None,
                json.dumps({
                    "FULLNAME": "John Doe",
                    "ADD1": "123 Anywhere Street",
                    "ADD2": "Anytown",
                    "BANK": "1",
                    "CHEQUENUMBER": "123456789",
                    "MICRCODE": "12345678912345678",
                    "NUMBER": "00123",
                    "BACKGROUND": "Photo",
                    "BACKGROUND_NUMBER": "1",
                    "VOID": "ON",
                }),
                "application/json",
            ),
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["task_id"]


def wait_for_image(task_id: str, timeout=300) -> str:
    start = time.time()

    while True:
        r = session.get(
            f"{API_BASE}/generation-status/{task_id}/",
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()

        image_url = payload.get("image_url")
        if image_url:
            return image_url

        if time.time() - start > timeout:
            raise TimeoutError("Image generation timeout")

        time.sleep(2)

# ========= GENERATOR 2 (FINAL, NO PREVIEW) =========

def generate_task_gen2(data: dict, image_bytes: BytesIO) -> str:
    files = {
        "generator": (None, "uk_passport_new_fast"),  # YOUR GENERATOR SLUG
        "data": (
            None,
            json.dumps(data),
            "application/json",
        ),
        "image1": (
            "input.jpg",
            image_bytes,
            "image/jpeg",
        ),
    }

    r = session.post(
        f"{API_BASE}/generate/",
        files=files,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["task_id"]


def pay_for_result(task_id: str):
    r = session.post(
        f"{API_BASE}/pay-for-result/",
        json={"task_id": task_id},
        timeout=30,
    )
    r.raise_for_status()

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
        "📸 Image received.\n"
        "Now run:\n"
        "/test2 LN=DOE FN=\"JOHN LEE\" DOB=123456 SEX=M"
    )


async def test(update, context: ContextTypes.DEFAULT_TYPE):
    loop = asyncio.get_running_loop()

    try:
        await update.message.reply_text("🚀 Generating (generator 1)…")

        task_id = await loop.run_in_executor(None, generate_task_gen1)

        image_url = await loop.run_in_executor(
            None, lambda: wait_for_image(task_id)
        )

        photo = await loop.run_in_executor(
            None, lambda: download_image_to_memory(image_url)
        )

        await update.message.reply_photo(
            photo=photo,
            caption="🧪 GENERATOR 1 RESULT",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ ERROR:\n{e}")


async def test2(update, context: ContextTypes.DEFAULT_TYPE):
    loop = asyncio.get_running_loop()
    user_id = update.effective_user.id

    try:
        if user_id not in user_images:
            await update.message.reply_text("❌ Please send an image first.")
            return

        if not context.args:
            await update.message.reply_text(
                "Usage:\n"
                "/test2 LN=DOE FN=\"JOHN LEE\" DOB=123456 SEX=M"
            )
            return

        data = parse_kv_args(" ".join(context.args))

        await update.message.reply_text("💳 Generating & paying (generator 2)…")

        task_id = await loop.run_in_executor(
            None,
            lambda: generate_task_gen2(
                data,
                user_images[user_id]
            ),
        )

        await loop.run_in_executor(
            None,
            lambda: pay_for_result(task_id)
        )

        image_url = await loop.run_in_executor(
            None,
            lambda: wait_for_image(task_id)
        )

        photo = await loop.run_in_executor(
            None,
            lambda: download_image_to_memory(image_url)
        )

        await update.message.reply_photo(
            photo=photo,
            caption="✅ GENERATOR 2 FINAL (PAID)",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ ERROR:\n{e}")

# ========= APP =========

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("test", test))
app.add_handler(CommandHandler("test2", test2))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

app.run_polling()