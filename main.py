import logging
import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from yt_dlp import YoutubeDL

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def download_youtube_audio(video_id: str, filename: str) -> bool:
    """YouTube videodan audio yuklab olish."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': '/usr/bin/ffmpeg',  # FFmpeg yo'lini o'zgartiring agar kerak bo'lsa
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logger.error(f"Error downloading audio for video_id {video_id}: {str(e)}")
        return False

async def send_file(update: Update, file_path: str, title: str) -> bool:
    """Faylni Telegram orqali yuborish va keyin o'chirish."""
    try:
        with open(file_path, 'rb') as audio:
            await update.message.reply_audio(audio=audio, title=title, timeout=60)
        os.remove(file_path)
        return True
    except Exception as e:
        logger.error(f"Failed to send audio {file_path}: {str(e)}")
        return False

async def process_youtube_download(update: Update, msg, video_id: str, filename: str, title: str) -> None:
    """YouTube audioni yuklash va yuborish jarayoni."""
    logger.info(f"Downloading YouTube audio: {video_id} - {title}")

    success = await download_youtube_audio(video_id, filename)
    if success and os.path.exists(f"{filename}.mp3"):
        logger.info("Download successful, sending file")
        sent = await send_file(update, f"{filename}.mp3", title)
        if sent:
            await msg.delete()
        else:
            await msg.edit_text("❌ Audio yuborishda xato yuz berdi.")
    else:
        await msg.edit_text("❌ Audio yuklashda xato yuz berdi.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi xabarini qayta ishlash."""
    query = update.message.text.strip()
    if not query:
        return

    logger.info(f"Received query: {query}")
    msg = await update.message.reply_text("🔍 Qidirilmoqda...")

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'default_search': 'ytsearch1',
        'noplaylist': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info and info['entries']:
                video = info['entries'][0]
            else:
                video = info

        video_id = video.get("id")
        title = video.get("title", "Unknown Title")
        if not video_id:
            raise ValueError("Video ID not found")

        filename = "".join(c for c in f"{title}_{video_id}" if c.isalnum() or c in (' ', '_')).replace(" ", "_")

        await msg.edit_text("⬇️ Yuklanmoqda...")
        await process_youtube_download(update, msg, video_id, filename, title)

    except Exception as e:
        logger.error(f"Search failed for query '{query}': {str(e)}")
        await msg.edit_text("❌ Qo‘shiq topilmadi yoki xato yuz berdi.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushirish komandasi."""
    await update.message.reply_text("🎵 Salom! Menga qo‘shiq nomini yoki YouTube linkini yuboring, men sizga MP3 yuboraman.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xatolarni ushlash va log qilish."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ Botda xato yuz berdi, iltimos qayta urinib ko‘ring.")

async def run_bot() -> None:
    """Botni ishga tushirish uchun asosiy korutina."""
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlerlarni qo'shish
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Bot started polling...")
    try:
        await application.run_polling(allowed_updates=Update.ALL_TYPES, timeout=30)
    except Exception as e:
        logger.error(f"Polling xatosi: {str(e)}")
        raise

def main() -> None:
    """Botni ishga tushirish."""
    retry_count = 0
    retry_limit = 5
    retry_delay = 5  # sekund

    while retry_count < retry_limit:
        try:
            asyncio.run(run_bot())
            break
        except Exception as e:
            logger.error(f"Botni ishga tushirishda xatolik: {str(e)}")
            retry_count += 1
            if retry_count < retry_limit:
                logger.info(f"Qayta urinish {retry_count+1}/{retry_limit} {retry_delay} sekunddan so‘ng...")
                time.sleep(retry_delay)
            else:
                logger.error("Qayta urinishlar chegarasi oshdi. Bot to‘xtadi.")
                raise

if __name__ == '__main__':
    main()