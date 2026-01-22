import os
import json
import time
import asyncio
import requests
from io import BytesIO
from requests.auth import HTTPBasicAuth
from telegram.ext import Application, CommandHandler

# ========= ENV =========

BOT_TOKEN = os.getenv("BOT_TOKEN")
VERIF_LOGIN = os.getenv("VERIF_LOGIN")
VERIF_PASSWORD = os.getenv("VERIF_PASSWORD")

API_BASE = "https://api.veriftools.fans/api/integration"
AUTH = HTTPBasicAuth(VERIF_LOGIN, VERIF_PASSWORD)

# ========= API HELPERS =========

def generate_task():
    r = requests.post(
        f"{API_BASE}/generate/",
        auth=AUTH,
        files={
            "generator": (None, "bank_check"),
            "data": (None, json.dumps({
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
            }), "application/json"),
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["task_id"]


def wait_and_get_watermark(task_id):
    while True:
        r = requests.get(
            f"{API_BASE}/generation-status/{task_id}/",
            auth=AUTH,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        # ✅ THIS IS THE REAL CONDITION
        if "image_url" in data and data["image_url"]:
            return data["image_url"]

        time.sleep(2)


def download_to_memory(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    bio = BytesIO(r.content)
    bio.name = "preview.jpg"
    bio.seek(0)
    return bio

# ========= TELEGRAM COMMAND =========

async def test(update, context):
    loop = asyncio.get_running_loop()

    try:
        await update.message.reply_text("🚀 Generating (NO PAYMENT)…")

        task_id = await loop.run_in_executor(None, generate_task)
        await update.message.reply_text(f"🧩 Task ID: {task_id}")

        await update.message.reply_text("⏳ Waiting for preview…")
        image_url = await loop.run_in_executor(
            None, lambda: wait_and_get_watermark(task_id)
        )

        await update.message.reply_text("📥 Downloading watermark…")
        photo = await loop.run_in_executor(
            None, lambda: download_to_memory(image_url)
        )

        await update.message.reply_photo(
            photo=photo,
            caption="🧪 WATERMARKED PREVIEW (NO PAYMENT)",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ ERROR:\n{e}")

# ========= APP =========

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("test", test))
app.run_polling()