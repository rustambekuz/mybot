import os
import re
import logging
import html
import importlib
import aiofiles
import time
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Forbidden
import googleapiclient.discovery
import yt_dlp
import instaloader
from uuid import uuid4
from dotenv import load_dotenv

# .env faylidan kalitlarni o‘qish
load_dotenv()

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API sozlamalari
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DEVELOPER_KEY = os.getenv("YOUTUBE_API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Kalitlar mavjudligini tekshirish
if not DEVELOPER_KEY or not TOKEN:
    logger.error("YOUTUBE_API_KEY yoki TELEGRAM_TOKEN .env faylida topilmadi!")
    raise ValueError("API kalitlari yoki token sozlanmagan!")

# YouTube API ulanish
try:
    youtube = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, developerKey=DEVELOPER_KEY, cache_discovery=False
    )
except Exception as e:
    logger.error(f"YouTube API ulanishda xato: {e}")
    raise

# Instaloader sozlamalari
L = instaloader.Instaloader()

def clean_title(title: str) -> str:
    """YouTube yoki Instagram sarlavhasini tozalash"""
    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist, song = "", title

    song = re.sub(r'\s*\|.*$', '', song)
    song = re.sub(r'\s*Video Clip.*$', '', song, flags=re.IGNORECASE)
    song = re.sub(r'■.*$', '', song)
    song = re.sub(r'\s*\.*?\)', '', song)
    song = re.sub(r'\s+', ' ', song).strip()

    song = html.unescape(song).replace("'", "'")
    artist = html.unescape(artist).replace("'", "'")

    return f"{artist} - {song}" if artist else song

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushirish uchun /start buyrug'i"""
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini yuboring (masalan: Hamdam Sobirov - Tentakcham) yoki YouTube/Instagram havolasini yuboring.\n"
        "Iltimos, xonanda nomini imlo xatosiz yozing!"
    )

async def download_youtube_audio(video_id: str, filename: str) -> bool:
    """YouTube videodan audio yuklab olish"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'cookies': '/home/rustambek/PycharmProjects/MusiqaBot/youtube_cookies.txt',
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
        logger.error(f"YouTube audio yuklashda xato: {e}")
        return False

async def download_instagram_media(post_url: str, filename: str) -> tuple[bool, str]:
    """Instagram postdan media yuklab olish"""
    try:
        shortcode = post_url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=filename)

        # Video yoki rasm topish
        for file in os.listdir(filename):
            if file.endswith(('.mp4', '.jpg')):
                media_path = os.path.join(filename, file)
                if file.endswith('.mp4'):
                    return True, media_path
                else:
                    return False, media_path  # Rasm bo‘lsa, audio emas
        return False, ""
    except Exception as e:
        logger.error(f"Instagram media yuklashda xato: {e}")
        return False, ""

async def search_youtube(query: str) -> tuple[str, str]:
    """YouTube’da qo‘shiq qidirish"""
    try:
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=1
        )
        response = request.execute()
        if response.get("items"):
            item = response["items"][0]
            return item["id"]["videoId"], clean_title(item["snippet"]["title"])
        return "", ""
    except Exception as e:
        logger.error(f"YouTube API xatosi: {e}")
        return "", ""

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi so‘rovini qayta ishlash"""
    query_text = update.message.text
    await update.message.reply_text("🔎 Qidirilmoqda, biroz kuting...")

    # Havola ekanligini tekshirish
    is_youtube = "youtube.com" in query_text or "youtu.be" in query_text
    is_instagram = "instagram.com" in query_text

    filename = f"media_{uuid4().hex}"
    title = query_text

    if is_youtube:
        # YouTube havolasi
        video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", query_text)
        if video_id:
            video_id = video_id.group(1)
        else:
            await update.message.reply_text("❌ Noto‘g‘ri YouTube havolasi!")
            return
    elif is_instagram:
        # Instagram havolasi
        await update.message.reply_text(f"⬇️ Instagram’dan yuklanmoqda: {title}")
        success, media_path = await download_instagram_media(query_text, filename)
        if success and media_path.endswith('.mp4'):
            try:
                async with aiofiles.open(media_path, 'rb') as media:
                    await update.message.reply_video(
                        video=await media.read(),
                        caption=f"🎥 {title}",
                        filename=f"{title}.mp4"
                    )
            except Exception as e:
                logger.error(f"Instagram media yuborishda xato: {e}")
                await update.message.reply_text("❌ Media yuborishda xato yuz berdi.")
            finally:
                if os.path.exists(media_path):
                    os.remove(media_path)
                if os.path.exists(filename):
                    for file in os.listdir(filename):
                        os.remove(os.path.join(filename, file))
                    os.rmdir(filename)
            return
        else:
            await update.message.reply_text("❌ Instagram’dan video yuklashda xato yuz berdi yoki bu rasm!")
            return
    else:
        # Qo‘shiq nomi bo‘lsa, YouTube’da qidirish
        video_id, title = await search_youtube(query_text)
        if not video_id:
            await update.message.reply_text("❌ Hech narsa topilmadi. Boshqa so‘rov yuborib ko‘ring.")
            return

    # YouTube’dan audio yuklash
    await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
    if await download_youtube_audio(video_id, filename):
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
            if os.path.exists(f"{filename}.mp3"):
                os.remove(f"{filename}.mp3")
    else:
        await update.message.reply_text("❌ Audio yuklashda xato yuz berdi.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xatolarni ushlash va foydalanuvchiga xabar berish"""
    logger.error(f"Xato yuz berdi: {context.error}")
    if isinstance(context.error, Forbidden):
        logger.warning("Bot foydalanuvchi tomonidan bloklangan. Xabar yuborilmaydi.")
        return
    if update and update.message:
        try:
            await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko‘ring.")
        except Forbidden:
            logger.warning("Bot bloklangan, xabar yuborib bo‘lmadi.")
        except Exception as e:
            logger.error(f"Xato xabarini yuborishda xato: {e}")

def verify_dependencies():
    """Kerakli kutubxonalarni tekshirish"""
    required_packages = [
        ('python-telegram-bot', 'telegram'),
        ('google-api-python-client', 'googleapiclient'),
        ('yt-dlp', 'yt_dlp'),
        ('instaloader', 'instaloader'),
        ('aiofiles', 'aiofiles'),
        ('python-dotenv', 'dotenv'),
        ('aiohttp', 'aiohttp')
    ]
    missing = []
    for package, module in required_packages:
        try:
            importlib.import_module(module)
            logger.info(f"{package} (modul: {module}) muvaffaqiyatli topildi")
        except ImportError as e:
            logger.error(f"{package} (modul: {module}) topilmadi: {e}")
            missing.append(package)
    return missing

def main() -> None:
    """Botni ishga tushirish"""
    missing_packages = verify_dependencies()
    if missing_packages:
        logger.error(f"Quyidagi kutubxonalar o'rnatilmagan: {', '.join(missing_packages)}")
        logger.error("Iltimos, ularni o'rnating: pip install -r requirements.txt")
        return

    max_retries = 3
    retry_count = 0
    retry_delay = 5

    while retry_count < max_retries:
        try:
            application = (
                Application.builder()
                .token(TOKEN)
                .get_updates_read_timeout(30)
                .get_updates_write_timeout(30)
                .get_updates_connect_timeout(30)
                .get_updates_pool_timeout(30)
                .build()
            )

            application.add_handler(CommandHandler("start", start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_media))
            application.add_error_handler(error_handler)

            logger.info("Bot ishga tushdi...")

            application.run_polling(allowed_updates=Update.ALL_TYPES)
            break
        except TimeoutError as e:
            retry_count += 1
            logger.error(f"Timeout xatosi ({retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                logger.info(f"Qayta ulanish {retry_delay} soniyadan keyin...")
                time.sleep(retry_delay)
            else:
                logger.error("Maksimal qayta ulanish soni tugadi")
        except Exception as e:
            logger.error(f"Botni ishga tushirishda xato: {str(e)}")
            break

if __name__ == "__main__":
    main()