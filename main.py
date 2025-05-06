import os
import logging
import asyncio
import aiofiles
from uuid import uuid4
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL

# .env faylini yuklash
load_dotenv()

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram tokenini olish
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN .env faylida topilmadi!")
    raise ValueError("Bot tokeni sozlanmagan!")

# /start komandasi uchun handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Salom! Menga YouTube havolasini yuboring, men esa sizga audio faylni yuboraman."
    )

# Audio yuklab olish funksiyasi
async def download_audio(url: str, filename: str) -> tuple[bool, str]:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    # Agar cookies.txt fayli mavjud bo‘lsa, uni qo‘shish
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            title = info_dict.get('title', 'Audio fayl')
        return True, title
    except Exception as e:
        logger.error(f"Audio yuklashda xato: {e}")
        return False, ""

# Foydalanuvchi xabarlarini qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text.strip()
    await update.message.reply_text("🔎 Yuklanmoqda, biroz kuting...")

    filename = f"audio_{uuid4().hex}"
    success, title = await download_audio(url, filename)
    if success:
        try:
            async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                await update.message.reply_audio(
                    audio=await audio.read(),
                    caption=f"🎵 {title}",
                    title=title
                )
        except Exception as e:
            logger.error(f"Audio yuborishda xato: {e}")
            await update.message.reply_text("❌ Audio yuborishda xato yuz berdi.")
        finally:
            if os.path.exists(f"{filename}.mp3"):
                os.remove(f"{filename}.mp3")
    else:
        await update.message.reply_text("❌ Audio yuklashda xato yuz berdi.")

# Xatolarni qayta ishlash
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Xato yuz berdi: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko‘ring.")

# Botni ishga tushirish
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
