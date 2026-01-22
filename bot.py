import os
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from veriftools import veriftools

# ========= ENV =========
BOT_TOKEN = os.getenv("BOT_TOKEN")

USER = {
    "login": os.getenv("VERIF_LOGIN"),
    "password": os.getenv("VERIF_PASSWORD"),
}

PASSPORT_GENERATOR_URL = "https://verif.tools/uk_passport/"
TEST_GENERATOR_URL = "https://api.veriftools.fans/en/bank_check/"

# ========= COMMANDS =========

async def start(update, context):
    await update.message.reply_text(
        "Welcome!\n\n"
        "Commands:\n"
        "/gen  – generate passport image (requires photo)\n"
        "/test – run API test generator"
    )


async def gen(update, context):
    context.user_data.clear()
    context.user_data["step"] = "await_photo"
    context.user_data["data"] = {
        "SURNAME": "DOE",
        "GIVENNAME": "JOHN",
        "DOB": "02.05.1960",
        "POB": "LONDON",
    }

    await update.message.reply_text("Please send the face photo.")


async def photo_handler(update, context):
    if context.user_data.get("step") != "await_photo":
        await update.message.reply_text("Use /gen first.")
        return

    await update.message.reply_text("Processing, please wait...")

    # ---- Save photo ----
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    await tg_file.download_to_drive("photo.jpg")

    images = {"image1": "./photo.jpg"}
    loop = asyncio.get_running_loop()

    try:
        url = await loop.run_in_executor(
            None,
            lambda: veriftools.generate_image(
                PASSPORT_GENERATOR_URL,
                USER,
                context.user_data["data"],
                images,
            ),
        )

        if not url:
            await update.message.reply_text("Generation failed: no image returned.")
            return

        await loop.run_in_executor(
            None,
            lambda: veriftools.download_image(url, "result_image.jpg"),
        )

        await update.message.reply_photo(
            open("result_image.jpg", "rb"),
            caption="✅ Generation successful",
        )

    except KeyError:
        await update.message.reply_text(
            "Generation failed: API access or balance issue."
        )

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

    finally:
        # ---- Cleanup ----
        if os.path.exists("photo.jpg"):
            os.remove("photo.jpg")
        if os.path.exists("result_image.jpg"):
            os.remove("result_image.jpg")

        context.user_data.clear()


async def test_command(update, context):
    await update.message.reply_text("Running test generator, please wait...")

    data = {
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
    }

    loop = asyncio.get_running_loop()

    try:
        url = await loop.run_in_executor(
            None,
            lambda: veriftools.generate_image(
                TEST_GENERATOR_URL,
                USER,
                data,
                {},
            ),
        )

        if not url:
            await update.message.reply_text("Test failed: no image returned.")
            return

        await loop.run_in_executor(
            None,
            lambda: veriftools.download_image(url, "test_result.jpg"),
        )

        await update.message.reply_photo(
            open("test_result.jpg", "rb"),
            caption="✅ Test generation successful",
        )

    except KeyError:
        await update.message.reply_text(
            "Test failed: API access or balance issue."
        )

    except Exception as e:
        await update.message.reply_text(f"Test failed: {str(e)}")

    finally:
        if os.path.exists("test_result.jpg"):
            os.remove("test_result.jpg")


# ========= APP =========

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("gen", gen))
app.add_handler(CommandHandler("test", test_command))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

app.run_polling(close_loop=False)