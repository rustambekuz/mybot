import logging
import os
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from yt_dlp import YoutubeDL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def download_youtube_audio(video_id: str, filename: str) -> bool:
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
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logger.error("Error downloading audio", exc_info=True)
        return False


async def send_file(update: Update, file_path: str, title: str) -> bool:
    try:
        with open(file_path, 'rb') as audio:
            await update.message.reply_audio(audio=audio, title=title)
        os.remove(file_path)
        return True
    except Exception as e:
        logger.error("Failed to send audio", exc_info=True)
        return False


async def process_youtube_download(update: Update, msg, video_id: str, filename: str, title: str) -> None:
    logger.info(f"Downloading YouTube audio: {video_id} - {title}")

    success = await download_youtube_audio(video_id, filename)
    if success:
        logger.info("Download successful, sending file")
        sent = await send_file(update, f"{filename}.mp3", title)
        if sent:
            await msg.delete()
    else:
        await msg.edit_text("❌ Audio yuklashda xato yuz berdi.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text.strip()
    if not query:
        return

    logger.info(f"Received query: {query}")
    msg = await update.message.reply_text("🔍 Qidirilmoqda...")

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'default_search': 'ytsearch1',
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                video = info['entries'][0]
            else:
                video = info

        video_id = video.get("id")
        title = video.get("title")
        filename = f"{title}_{video_id}".replace(" ", "_")

        await msg.edit_text("⬇️ Yuklanmoqda...")
        await process_youtube_download(update, msg, video_id, filename, title)

    except Exception as e:
        logger.error("Search failed", exc_info=True)
        await msg.edit_text("❌ Qo‘shiq topilmadi.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🎵 Salom! Menga qo‘shiq nomini yoki YouTube linkini yuboring, men sizga MP3 yuboraman.")


def main() -> None:
    BOT_TOKEN = "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4"  # <-- Bu yerga o‘z tokeningizni yozing
    retry_count = 0
    retry_limit = 5
    retry_delay = 5  # sekund

    while retry_count < retry_limit:
        try:
            application = ApplicationBuilder().token(BOT_TOKEN).build()

            application.add_handler(CommandHandler("start", start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

            logger.info("Bot started polling...")
            application.run_polling()
            break

        except Exception as e:
            logger.error("Botni ishga tushirishda xatolik yuz berdi", exc_info=True)
            retry_count += 1
            time.sleep(retry_delay)


if __name__ == '__main__':
    main()
