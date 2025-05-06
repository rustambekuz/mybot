import os
import logging
import asyncio
from uuid import uuid4
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL
import aiofiles

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome_text = (
        f"<b>🎧 Salom, {user.first_name}!</b>\n\n"
        "Men sizga <b>YouTube</b> va <b>Instagram</b> havolalaridan audio fayllarni yuklab beraman.\n"
        "Iltimos, quyidagi ko'rsatmalarga rioya qiling:\n"
        "1️⃣ Yuklab olishni istagan <b>video havolasini</b> yuboring.\n"
        "2️⃣ Men sizga audio faylni yuboraman.\n\n"
        "🎶 <i>Masalan:</i> https://www.youtube.com/watch?v=abc123 yoki https://www.instagram.com/reel/xyz456\n\n"
        "Agar savollaringiz bo'lsa, bemalol so'rang!"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def download_audio(url: str, filename: str) -> tuple[bool, str]:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            title = info_dict.get('title', 'Audio')
        return True, title
    except Exception as e:
        logger.error(f"Audio yuklashda xato: {e}")
        return False, ""

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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Xatolik yuz berdi:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko'ring.")

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
