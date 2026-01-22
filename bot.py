import requests
from requests.auth import HTTPBasicAuth
import time

async def test_command(update, context):
    await update.message.reply_text("Running API test, please wait...")

    auth = HTTPBasicAuth(
        os.getenv("VERIF_LOGIN"),
        os.getenv("VERIF_PASSWORD")
    )

    payload = {
        "generator": "bank_check",
        "data": {
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
        "images": {}
    }

    loop = asyncio.get_running_loop()

    try:
        # ---- CREATE TASK ----
        r = await loop.run_in_executor(
            None,
            lambda: requests.post(
                "https://api.veriftools.fans/api/integration/generate/",
                json=payload,
                auth=auth,
                timeout=30
            )
        )
        r.raise_for_status()
        task_id = r.json()["task_id"]

        # ---- POLL STATUS ----
        while True:
            s = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    f"https://api.veriftools.fans/api/integration/generation-status/{task_id}/",
                    auth=auth,
                    timeout=30
                )
            )
            s.raise_for_status()
            status = s.json()

            if status["status"] == "DONE":
                result_url = status["result"]
                break

            if status["status"] == "ERROR":
                raise Exception(status)

            await asyncio.sleep(2)

        # ---- DOWNLOAD RESULT ----
        img = await loop.run_in_executor(
            None,
            lambda: requests.get(result_url, timeout=30)
        )
        img.raise_for_status()

        with open("test_result.jpg", "wb") as f:
            f.write(img.content)

        await update.message.reply_photo(
            open("test_result.jpg", "rb"),
            caption="✅ API test successful"
        )

        os.remove("test_result.jpg")

    except Exception as e:
        await update.message.reply_text(f"API error: {repr(e)}")