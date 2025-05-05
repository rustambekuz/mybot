import asyncio
import requests
import logging
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API sozlamalari (RapidAPI orqali)
MUSIC_API_URL = "https://baixar-musicas-mp3-completas.p.rapidapi.com/download"  # Yangilangan endpoint
RAPIDAPI_KEY = "cc1b311428msh8e7eac8a9647690p1aea34jsnb448080c73a6"
RAPIDAPI_HOST = "baixar-musicas-mp3-completas.p.rapidapi.com"

# Telegram bot tokeni (foydalanuvchi tokenini qo‘ying)
TOKEN = "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4"

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi yuborgan so'rov bo'yicha musiqani qidirish va yuklab olish"""
    query_text = update.message.text
    await update.message.reply_text("🔎 Qidirilmoqda, biroz kuting...")

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    params = {
        "query": query_text  # API’ga qarab parametrlarni o‘zgartirish kerak bo‘lishi mumkin
    }

    try:
        logger.info(f"API so'rovi yuborildi: {MUSIC_API_URL}?query={query_text}")
        response = requests.get(MUSIC_API_URL, headers=headers, params=params)
        logger.info(f"API javobi: {response.status_code} - {response.text[:500]}")

        if response.status_code != 200:
            logger.error(f"Music API xatosi: HTTP {response.status_code}")
            await update.message.reply_text(f"❌ API xatosi: HTTP {response.status_code}. Keyinroq urinib ko'ring.")
            return

        data = response.json()
        if not data or 'download_url' not in data:
            logger.error(f"API javobi noto'g'ri formatda: {data}")
            await update.message.reply_text("❌ API javobi noto'g'ri formatda. Keyinroq urinib ko'ring.")
            return

        results = data.get('results', [])
        if not results:
            await update.message.reply_text("❌ Hech narsa topilmadi. Boshqa so'rov yuborib ko'ring.")
            return

        # Birinchi natijani olish
        track = results[0]
        title = track.get('title', 'Unknown Title')
        artist = track.get('artist', 'Unknown Artist')
        download_url = track.get('download_url')

        if not download_url:
            await update.message.reply_text(
                f"🎵 Topildi: {artist} - {title}\n"
                "❌ Yuklab olish linki mavjud emas."
            )
            return

        await update.message.reply_text(
            f"🎵 Topildi: {artist} - {title}\n"
            f"⬇️ Yuklab olish: {download_url}"
        )
        logger.info(f"Muvaffaqiyatli: {artist} - {title}")

    except Exception as e:
        logger.error(f"Qidiruvda xato: {e}")
        await update.message.reply_text(f"❌ Muammo yuz berdi: {str(e)}. Keyinroq urinib ko'ring.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushirish uchun /start buyrug'i"""
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini yuboring, masalan: Shaxzoda - Hayot Ayt\n"
        "Bot qo'shiqni qidiradi va yuklab olish linkini yuboradi."
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xatolarni ushlash va foydalanuvchiga xabar berish"""
    logger.error(f"Xato yuz berdi: {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko'ring.")

async def main() -> None:
    """Botni ishga tushirish"""
    global application
    try:
        application = Application.builder().token(TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
        application.add_error_handler(error_handler)

        logger.info("Bot ishga tushdi...")

        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=10
        )

        while True:
            await asyncio.sleep(3600)

    except Exception as e:
        logger.error(f"Botni ishga tushirishda xato: {e}")
        raise
    finally:
        if 'application' in locals():
            logger.info("Bot to'xtatilmoqda...")
            await application.stop()
            await application.shutdown()
            logger.info("Bot muvaffaqiyatli to'xtatildi.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        logger.error(f"Event loop xatosi: {e}")
        raise