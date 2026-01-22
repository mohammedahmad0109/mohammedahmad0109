import os
import asyncio
import time
import requests
from requests.auth import HTTPBasicAuth
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
VERIF_LOGIN = os.getenv("VERIF_LOGIN")
VERIF_PASSWORD = os.getenv("VERIF_PASSWORD")

API_BASE = "https://api.veriftools.fans/api/integration"

auth = HTTPBasicAuth(VERIF_LOGIN, VERIF_PASSWORD)

# ================== HELPERS ==================

def create_task(generator, data, image_path=None):
    files = {}
    payload = {
        "generator": generator,
        "data": (None, str(data), "application/json"),
    }

    if image_path:
        files["image1"] = open(image_path, "rb")

    r = requests.post(
        f"{API_BASE}/generate/",
        files={**payload, **files},
        auth=auth,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["task_id"]


def wait_for_ready(task_id):
    while True:
        r = requests.get(
            f"{API_BASE}/generation-status/{task_id}/",
            auth=auth,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        if data["status"] in ("READY", "DONE"):
            return data

        if data["status"] == "ERROR":
            raise Exception(data)

        time.sleep(2)


def pay_for_result(task_id):
    r = requests.post(
        f"{API_BASE}/pay-for-result/",
        json={"task_id": task_id},
        auth=auth,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["image_url"]


def download_image(url, path):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

# ================== COMMANDS ==================

async def start(update, context):
    await update.message.reply_text(
        "Commands:\n"
        "/gen – passport generator (send photo)\n"
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
            lambda: create_task(
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

        await loop.run_in_executor(None, lambda: wait_for_ready(task_id))
        image_url = await loop.run_in_executor(None, lambda: pay_for_result(task_id))
        await loop.run_in_executor(None, lambda: download_image(image_url, "result.jpg"))

        await update.message.reply_photo(
            open("result.jpg", "rb"),
            caption="✅ Passport generated",
        )

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

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
            lambda: create_task(
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

        await loop.run_in_executor(None, lambda: wait_for_ready(task_id))
        image_url = await loop.run_in_executor(None, lambda: pay_for_result(task_id))
        await loop.run_in_executor(None, lambda: download_image(image_url, "test.jpg"))

        await update.message.reply_photo(
            open("test.jpg", "rb"),
            caption="✅ API test successful",
        )

    except Exception as e:
        await update.message.reply_text(f"Test failed: {e}")

    finally:
        if os.path.exists("test.jpg"):
            os.remove("test.jpg")

# ================== APP ==================

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("gen", gen))
app.add_handler(CommandHandler("test", test_command))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

app.run_polling()