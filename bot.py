import os
import json
import asyncio
import requests
from requests.auth import HTTPBasicAuth
from telegram.ext import Application, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
VERIF_LOGIN = os.getenv("VERIF_LOGIN")
VERIF_PASSWORD = os.getenv("VERIF_PASSWORD")

API_BASE = "https://api.veriftools.fans/api/integration"
AUTH = HTTPBasicAuth(VERIF_LOGIN, VERIF_PASSWORD)

# ---------- API HELPERS (SYNC, CURL-EQUIVALENT) ----------

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


def wait_until_done(task_id):
    while True:
        r = requests.get(
            f"{API_BASE}/generation-status/{task_id}/",
            auth=AUTH,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        if data.get("task_status") == "end":
            return

        # IMPORTANT: do NOT time.sleep in async thread
        import time
        time.sleep(1)


def pay_and_get_image(task_id):
    r = requests.post(
        f"{API_BASE}/pay-for-result/",
        auth=AUTH,
        json={"task_id": task_id},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["image_url"]


def download_image(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open("result.jpg", "wb") as f:
        f.write(r.content)

# ---------- TELEGRAM COMMAND ----------

async def test(update, context):
    await update.message.reply_text("🚀 Starting generation (curl-exact flow)…")

    loop = asyncio.get_running_loop()

    try:
        task_id = await loop.run_in_executor(None, generate_task)
        await update.message.reply_text(f"🧩 Task ID: {task_id}")

        await loop.run_in_executor(None, lambda: wait_until_done(task_id))
        await update.message.reply_text("💳 Paying for result…")

        image_url = await loop.run_in_executor(None, lambda: pay_and_get_image(task_id))
        await update.message.reply_text("📥 Downloading image…")

        await loop.run_in_executor(None, lambda: download_image(image_url))

        with open("result.jpg", "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption="✅ GENERATED SUCCESSFULLY (IDENTICAL TO CURL)",
            )

    except Exception as e:
        await update.message.reply_text(f"❌ ERROR:\n{e}")

    finally:
        if os.path.exists("result.jpg"):
            os.remove("result.jpg")

# ---------- APP ----------

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("test", test))
app.run_polling()