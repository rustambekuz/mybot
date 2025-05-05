import os
import re
import logging
import html
import aiofiles
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import googleapiclient.discovery
import yt_dlp
from uuid import uuid4

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DEVELOPER_KEY = "AIzaSyBpGD78aAuu69-GhK8VHcdhs9PSqNzWaVM"
youtube = googleapiclient.discovery.build(API_SERVICE_NAME, API_VERSION, developerKey=DEVELOPER_KEY)

TOKEN = "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4"

def clean_title(title: str) -> str:
    """YouTube video sarlavhasini tozalash"""
    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist, song = "", title

    song = re.sub(r'\s*\|.*$', '', song)
    song = re.sub(r'\s*Video Clip.*$', '', song, flags=re.IGNORECASE)
    song = re.sub(r'■.*$', '', song)
    song = re.sub(r'\s*\(.*?\)', '', song)
    song = re.sub(r'\s+', ' ', song).strip()

    song = html.unescape(song).replace("'", "'")
    artist = html.unescape(artist).replace("'", "'")

    return f"{artist} - {song}" if artist else song

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushirish uchun /start buyrug'i"""
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini yuboring, masalan: Hamdam Sobirov - Tentakcham\n"
        "iltimos, qo'shiqchining izlayotganda imlo xatoga yo'l qo'ymang!"

    )

async def download_audio(video_id: str, filename: str) -> bool:
    """YouTube videodan audio yuklab olish"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        for ext in ['webm', 'm4a', 'mp3']:
            path = f"{filename}.{ext}"
            if os.path.exists(path):
                os.rename(path, f"{filename}.mp3")
                return True
        return False
    except Exception as e:
        logger.error(f"Audio yuklashda xato: {e}")
        return False

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi yuborgan so'rov bo'yicha musiqa qidirish va yuborish"""
    query_text = update.message.text
    await update.message.reply_text("🔎 Qidirilmoqda, biroz kuting...")

    try:
        request = youtube.search().list(
            part="snippet",
            q=query_text,
            type="video",
            maxResults=1
        )
        response = request.execute()
    except Exception as e:
        logger.error(f"YouTube API xatosi: {e}")
        await update.message.reply_text("❌ YouTube API bilan muammo yuz berdi. Keyinroq urinib ko'ring.")
        return

    if not response.get("items"):
        await update.message.reply_text("❌ Hech narsa topilmadi. Boshqa so'rov yuborib ko'ring.")
        return

    item = response["items"][0]
    video_id = item["id"]["videoId"]
    title = clean_title(item["snippet"]["title"])
    filename = f"audio_{uuid4().hex}"

    await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")

    if await download_audio(video_id, filename):
        try:
            async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                await update.message.reply_audio(
                    audio=await audio.read(),
                    title=title,
                    caption=f"🎵 {title}",
                    filename=f"{title}.mp3"
                )
        except Exception as e:
            logger.error(f"Audio yuborishda xato: {e}")
            await update.message.reply_text("❌ Audio yuborishda xato yuz berdi.")
        finally:
            # Faylni tozalash
            if os.path.exists(f"{filename}.mp3"):
                os.remove(f"{filename}.mp3")
    else:
        await update.message.reply_text("❌ Audio yuklashda xato yuz berdi.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xatolarni ushlash va foydalanuvchiga xabar berish"""
    logger.error(f"Xato yuz berdi: {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko'ring.")

def main() -> None:
    """Botni ishga tushirish"""
    try:
        application = Application.builder().token(TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
        application.add_error_handler(error_handler)

        logger.info("Bot ishga tushdi...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Botni ishga tushirishda xato: {e}")

if __name__ == "__main__":
    main()