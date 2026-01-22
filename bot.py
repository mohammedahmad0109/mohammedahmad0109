import os
import json
import time
import asyncio
import requests
from requests.auth import HTTPBasicAuth
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
VERIF_LOGIN = os.getenv("VERIF_LOGIN")
VERIF_PASSWORD = os.getenv("VERIF_PASSWORD")

API_BASE = "https://api.veriftools.fans/api/integration"
AUTH = HTTPBasicAuth(VERIF_LOGIN, VERIF_PASSWORD)

HEADERS = {
    "Accept": "application/json",
}

# ================= API HELPERS =================

def api_generate(generator: str, data: dict, image_path: str | None = None) -> str:
    files = {
        "generator": (None, generator),
        "data": (None, json.dumps(data), "application/json"),
    }

    image_file = None
    try:
        if image_path:
            image_file = open(image_path, "rb")
            files["image1"] = (
                os.path.basename(image_path),
                image_file,
                "image/jpeg",
            )

        r = requests.post(
            f"{API_BASE}/generate/",
            files=files,
            auth=AUTH,
            headers=HEADERS,
            timeout=30,
        )

        if r.status_code not in (200, 201):
            raise Exception(f"Generate failed {r.status_code}: {r.text}")

        return r.json()["task_id"]

    finally:
        if image_file:
            image_file.close()


def api_wait(task_id: str) -> dict:
    while True:
        r = requests.get(
            f"{API_BASE}/generation-status/{task_id}/",
            auth=AUTH,
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()

        status = payload.get("status")
        if status in ("READY", "DONE"):
            return payload

        if status == "ERROR":
            raise Exception(payload)

        time.sleep(2)


def api_pay(task_id: str) -> str:
    r = requests.post(
        f"{API_BASE}/pay-for-result/",
        json={"task_id": task_id},
        auth=AUTH,
        headers=HEADERS,
        timeout=30,
    )

    if r.status_code not in (200, 201):
        raise Exception(f"Payment failed {r.status_code}: {r.text}")

    return r.json()["image_url"]


def download_image(url: str, path: str):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

# ================= BOT COMMANDS =================

async def start(update, context):
    await update.message.reply_text(
        "/gen  – passport generator (send photo)\n"
        "/test – bank_check API test"
    )


async def gen(update, context):
    context.user_data.clear()
    context.user_data["await_photo"] = True
    await update.message.reply_text("Send face photo.")


async def photo_handler(update, context):
    if not context.user_data.get("await_photo"):
        await update.message.reply_text("Use /gen first.")
        return

    await update.message.reply_text("Processing...")

    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    await tg_file.download_to_drive("photo.jpg")

    loop = asyncio.get_running_loop()

    try:
        task_id = await loop.run_in_executor(
            None,
            lambda: api_generate(
                "uk_passport",
                {
                    "SURNAME": "DOE",
                    "GIVENNAME": "JOHN",
                    "DOB": "02.05.1960",
                    "POB": "LONDON",
                },
                "photo.jpg",
            ),
        )

        await loop.run_in_executor(None, lambda: api_wait(task_id))
        image_url = await loop.run_in_executor(None, lambda: api_pay(task_id))
        await loop.run_in_executor(None, lambda: download_image(image_url, "result.jpg"))

        await update.message.reply_photo(
            open("result.jpg", "rb"),
            caption="✅ Passport generated",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

    finally:
        for f in ("photo.jpg", "result.jpg"):
            if os.path.exists(f):
                os.remove(f)
        context.user_data.clear()


async def test_command(update, context):
    await update.message.reply_text("Running API test...")

    loop = asyncio.get_running_loop()

    try:
        task_id = await loop.run_in_executor(
            None,
            lambda: api_generate(
                "bank_check",
                {
                    "FULLNAME": "John Doe",
                    "ADD1": "123 Anywhere Street",
                    "ADD2": "Anytown, CA 12345",
                    "BANK": "1",
                    "CHEQUENUMBER": "123456789",
                    "MICRCODE": "12345678912345678",
                    "NUMBER": "00123",
                    "BACKGROUND": "Photo",
                    "BACKGROUND_NUMBER": "1",
                    "VOID": "ON",
                },
            ),
        )

        await loop.run_in_executor(None, lambda: api_wait(task_id))
        image_url = await loop.run_in_executor(None, lambda: api_pay(task_id))
        await loop.run_in_executor(None, lambda: download_image(image_url, "test.jpg"))

        await update.message.reply_photo(
            open("test.jpg", "rb"),
            caption="✅ API test successful",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

    finally:
        if os.path.exists("test.jpg"):
            os.remove("test.jpg")

# ================= APP =================

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("gen", gen))
app.add_handler(CommandHandler("test", test_command))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

app.run_polling()