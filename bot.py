import os
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from veriftools import veriftools

BOT_TOKEN = os.getenv("BOT_TOKEN")

user = {
    'login': os.getenv("VERIF_LOGIN"),
    'password': os.getenv("VERIF_PASSWORD")
}

generator_url = 'https://verif.tools/uk_passport/'

async def gen(update, context):
    context.user_data['step'] = 'await_photo'
    context.user_data['data'] = {
        'SURNAME': 'DOE',
        'GIVENNAME': 'JOHN',
        'DOB': '02.05.1960',
        'POB': 'LONDON',
    }
    await update.message.reply_text("Please send the face photo")

async def photo_handler(update, context):
    if context.user_data.get('step') != 'await_photo':
        return

    await update.message.reply_text("Processing, please wait...")

    photo = update.message.photo[-1]
    file = await photo.get_file()
    await file.download_to_drive('photo.jpg')

    images = {
        'image1': './photo.jpg'
    }

    loop = asyncio.get_running_loop()

    url = await loop.run_in_executor(
        None,
        lambda: veriftools.generate_image(
            generator_url,
            user,
            context.user_data['data'],
            images
        )
    )

    if url:
        await loop.run_in_executor(
            None,
            lambda: veriftools.download_image(url, 'result_image.jpg')
        )

        await update.message.reply_photo(
            open('result_image.jpg', 'rb')
        )
    else:
        await update.message.reply_text("Generation failed.")

    # cleanup
    import os
    os.remove('photo.jpg')
    os.remove('result_image.jpg')
    context.user_data.clear()

async def start(update, context):
    await update.message.reply_text("Use /gen to generate")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("gen", gen))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

app.run_polling()