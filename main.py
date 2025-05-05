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

api_service_name = "youtube"
api_version = "v3"
DEVELOPER_KEY = "AIzaSyBpGD78aAuu69-GhK8VHcdhs9PSqNzWaVM"
youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=DEVELOPER_KEY)

TOKEN = "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4"

def clean_title(title):
    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist = ""
        song = title

    song = re.sub(r'\s*\|.*$', '', song)
    song = re.sub(r'\s*Video Clip.*$', '', song, flags=re.IGNORECASE)
    song = re.sub(r'■.*$', '', song)
    song = re.sub(r'\s+', ' ', song).strip()
    song = re.sub(r'\s*\(.*?\)', '', song)

    song = html.unescape(song)
    song = song.replace("&#39;", "'")
    artist = html.unescape(artist)
    artist = artist.replace("&#39;", "'")

    return f"{artist} - {song}" if artist else song

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        await update.message.reply_text(
            f"Salom {user.first_name}!\n"
            "Qo'shiq nomini yuboring masalan quyidagicha "
            "(Hamdam Sobirov - Tentakcham)"
        )
    except Exception as e:
        logging.error(f"Start command error: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Qaytadan urinib ko'ring")

def download_audio(video_id, filename):
    """YouTube video-dan audio yuklab olish uchun yt_dlp ishlatish"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{filename}.%(ext)s',
        'cookiefile': 'cookies.txt',
        'quiet': True,
    }
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        for ext in ['webm', 'm4a', 'mp3']:
            path = f"{filename}.{ext}"
            if os.path.exists(path):
                os.rename(path, filename)
                return True
        return False
    except Exception as e:
        logging.error(f"Download error: {e}")
        return False

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("🔎 Qidirilmoqda biroz kuting...")
        query_text = update.message.text

        request = youtube.search().list(
            part="snippet",
            q=query_text,
            type="video",
            maxResults=1
        )

        try:
            response = request.execute()
        except Exception as e:
            logging.error(f"API chaqiruvi xatolik: {e}")
            await update.message.reply_text("API bilan aloqa muammosi yuzaga keldi. Qayta urinib ko'ring.")
            return

        if not response.get("items"):
            await update.message.reply_text("❌ Topilmadi. Iltimos, boshqacha yozib ko'ring.")
            return

        item = response["items"][0]
        video_id = item["id"]["videoId"]
        title = clean_title(item["snippet"]["title"])
        filename = f"audio_{video_id}"

        await update.message.reply_text(f"⬇️ Yuklab olinmoqda: {title}")

        if download_audio(video_id, filename):
            try:
                with open(filename, 'rb') as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=title,
                        caption=f"🎵 {title}"
                    )
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
        else:
            await update.message.reply_text("❌ Yuklab olishda xatolik yuz berdi.")

    except Exception as e:
        logging.error(f"Search music error: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")

def main():
    try:
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
        print("Bot ishga tushdi...")
        application.run_polling()
    except Exception as e:
        logging.error(f"Main function error: {e}")

if __name__ == "__main__":
    main()