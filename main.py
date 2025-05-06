import os
import logging
import asyncio
import aiofiles
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

load_dotenv()

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram tokeni
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN .env faylida topilmadi!")
    raise ValueError("TELEGRAM_TOKEN sozlanmagan!")

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Salom! YouTube havolasini yuboring, men esa sizga audio faylini yuboraman."
    )

# Audio yuklab olish funksiyasi
async def download_audio(url: str, filename: str) -> bool:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'cookiefile': 'cookies.txt',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logger.error(f"Audio yuklashda xato: {e}")
        return False

# Xabarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text.strip()
    await update.message.reply_text("🔎 Yuklanmoqda, biroz kuting...")

    filename = "audio_file"
    if await download_audio(url, filename):
        try:
            async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                await update.message.reply_audio(
                    audio=await audio.read(),
                    caption="🎵 Mana sizning audio faylingiz"
                )
        except Exception as e:
            logger.error(f"Audio yuborishda xato: {e}")
            await update.message.reply_text("❌ Audio yuborishda xato yuz berdi.")
        finally:
            if os.path.exists(f"{filename}.mp3"):
                os.remove(f"{filename}.mp3")
    else:
        await update.message.reply_text("❌ Audio yuklashda xato yuz berdi.")

# Botni ishga tushirish
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
