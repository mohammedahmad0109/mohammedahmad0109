import os
import json
import time
import asyncio
import requests
from requests.auth import HTTPBasicAuth
from telegram.ext import Application, CommandHandler, MessageHandler, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
VERIF_LOGIN = os.getenv("VERIF_LOGIN")
VERIF_PASSWORD = os.getenv("VERIF_PASSWORD")

API_BASE = "https://api.veriftools.fans/api/integration"
AUTH = HTTPBasicAuth(VERIF_LOGIN, VERIF_PASSWORD)
HEADERS = {"Accept": "application/json"}

# ---------- API ----------

def generate(generator, data):
    r = requests.post(
        f"{API_BASE}/generate/",
        auth=AUTH,
        headers=HEADERS,
        files={
            "generator": (None, generator),
            "data": (None, json.dumps(data), "application/json"),
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["task_id"]


def wait_until_end(task_id):
    while True:
        r = requests.get(
            f"{API_BASE}/generation-status/{task_id}/",
            auth=AUTH,
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()

        if payload.get("task_status") == "end":
            return payload

        time.sleep(2)


def pay(task_id):
    r = requests.post(
        f"{API_BASE}/pay-for-result/",
        auth=AUTH,
        headers=HEADERS,
        json={"task_id": task_id},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["image_url"]


def download(url, path):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

# ---------- BOT ----------

async def test(update, context):
    await update.message.reply_text("Running test (exact curl flow)...")

    loop = asyncio.get_running_loop()

    try:
        task_id = await loop.run_in_executor(
            None,
            lambda: generate(
                "bank_check",
                {
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
                },
            ),
        )

        await loop.run_in_executor(None, lambda: wait_until_end(task_id))
        image_url = await loop.run_in_executor(None, lambda: pay(task_id))
        await loop.run_in_executor(None, lambda: download(image_url, "result.jpg"))

        await update.message.reply_photo(
            open("result.jpg", "rb"),
            caption="✅ Generated exactly like curl",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

    finally:
        if os.path.exists("result.jpg"):
            os.remove("result.jpg")

# ---------- APP ----------

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("test", test))
app.run_polling()