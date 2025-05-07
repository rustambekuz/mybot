import os
import re
import logging
import html
import importlib
import aiofiles
import time
import aiohttp
import subprocess
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
    if not title:
        return "Unknown Title"

    # HTML belgilarni tozalash
    title = html.unescape(title)

    # Keraksiz qismlarni olib tashlash
    patterns = [
        r'\s*\(Official Video\).*',  # (Official Video)
        r'\s*\[Official Video\].*',  # [Official Video]
        r'\s*\(Official Music Video\).*',
        r'\s*\[Official Music Video\].*',
        r'\s*\|.*$',                 # | dan keyingi hamma narsa
        r'\s*Video Clip.*$',         # Video Clip
        r'\s*MV.*$',                 # MV
        r'🎵.*$',                    # Musiqa emojilari
        r'\s*\(\s*\).*',             # Bo‘sh qavslar ()
        r'\s*\[\s*\].*',             # Bo‘sh kvadrat qavslar []
    ]
    for pattern in patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    # Bir nechta bo‘shliqlarni olib tashlash
    title = re.sub(r'\s+', ' ', title).strip()

    # Xonanda va qo‘shiq nomini ajratish
    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist, song = "", title

    # Apostroflarni to‘g‘rilash
    song = song.replace("'", "'")
    artist = artist.replace("'", "'")

    # Telegram cheklovlari uchun uzunlikni qisqartirish
    song = song[:256]  # title uchun
    full_title = f"{artist} - {song}" if artist else song
    full_title = full_title[:1024]  # caption uchun

    logger.info(f"Tozalangan sarlavha: {full_title}")
    return full_title

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushirish uchun /start buyrug'i"""
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini yuboring (masalan: Hamdam Sobirov - Tentakcham) yoki YouTube/Instagram havolasini yuboring.\n"
        "Instagram havolalari uchun video va audio yuklab olishingiz mumkin!"
    )

async def download_youtube_audio(video_id: str, filename: str) -> bool:
    """YouTube videodan audio yuklab olish"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'cookies': '/home/rustambek/PycharmProjects/MusiqaBot/cookies.txt',
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

async def download_instagram_media(post_url: str, filename: str) -> tuple[bool, str, str, str]:
    """Instagram postdan media, audio va sarlavha yuklab olish"""
    try:
        shortcode = post_url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=filename)

        video_path = ""
        audio_path = f"{filename}.mp3"
        caption = post.caption or post.owner_username or "Instagram Post"
        caption = clean_title(caption[:100])  # Uzun tavsiflarni qisqartirish

        for file in os.listdir(filename):
            if file.endswith('.mp4'):
                video_path = os.path.join(filename, file)
                # Videodan audio ajratish
                cmd = [
                    'ffmpeg', '-i', video_path, '-vn', '-acodec', 'mp3',
                    '-ab', '192k', '-y', audio_path
                ]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                return True, video_path, audio_path, caption
            elif file.endswith('.jpg'):
                return False, os.path.join(filename, file), "", caption
        return False, "", "", caption
    except Exception as e:
        logger.error(f"Instagram media yuklashda xato: {e}")
        return False, "", "", ""

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
            raw_title = item["snippet"]["title"]
            logger.info(f"YouTube xom sarlavha: {raw_title}")
            return item["id"]["videoId"], clean_title(raw_title)
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

    if is_youtube:
        # YouTube havolasi
        video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", query_text)
        if video_id:
            video_id = video_id.group(1)
        else:
            await update.message.reply_text("❌ Noto‘g‘ri YouTube havolasi!")
            return
        # YouTube API orqali sarlavha olish
        try:
            request = youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()
            if response.get("items"):
                raw_title = response["items"][0]["snippet"]["title"]
                logger.info(f"YouTube xom sarlavha (havola): {raw_title}")
                title = clean_title(raw_title)
            else:
                title = query_text
        except Exception as e:
            logger.error(f"YouTube sarlavha olishda xato: {e}")
            title = query_text

        await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
        if await download_youtube_audio(video_id, filename):
            try:
                async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                    song_name = title.split(" - ")[-1] if " - " in title else title
                    await update.message.reply_audio(
                        audio=await audio.read(),
                        title=song_name[:256],
                        caption=f"🎵 {title}"[:1024],
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
    elif is_instagram:
        # Instagram havolasi
        await update.message.reply_text(f"⬇️ Instagram’dan yuklanmoqda...")
        success, media_path, audio_path, title = await download_instagram_media(query_text, filename)
        if success and media_path.endswith('.mp4') and audio_path:
            try:
                song_name = title.split(" - ")[-1] if " - " in title else title
                # Video yuborish
                async with aiofiles.open(media_path, 'rb') as video:
                    await update.message.reply_video(
                        video=await video.read(),
                        caption=f"🎥 {title} (Instagram Video)"[:1024],
                        filename=f"{title}.mp4"
                    )
                # Audio yuborish
                async with aiofiles.open(audio_path, 'rb') as audio:
                    await update.message.reply_audio(
                        audio=await audio.read(),
                        title=song_name[:256],
                        caption=f"🎵 {title} (Instagram Audio)"[:1024],
                        filename=f"{title}.mp3"
                    )
            except Exception as e:
                logger.error(f"Instagram media yuborishda xato: {e}")
                await update.message.reply_text("❌ Media yuborishda xato yuz berdi.")
            finally:
                if os.path.exists(media_path):
                    os.remove(media_path)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                if os.path.exists(filename):
                    for file in os.listdir(filename):
                        os.remove(os.path.join(filename, file))
                    os.rmdir(filename)
        else:
            await update.message.reply_text("❌ Instagram’dan media yuklashda xato yuz berdi yoki bu rasm!")
    else:
        # Qo‘shiq nomi bo‘lsa, YouTube’da qidirish
        video_id, title = await search_youtube(query_text)
        if not video_id:
            await update.message.reply_text("❌ Hech narsa topilmadi. Boshqa so‘rov yuborib ko‘ring.")
            return
        await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
        if await download_youtube_audio(video_id, filename):
            try:
                async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                    song_name = title.split(" - ")[-1] if " - " in title else title
                    await update.message.reply_audio(
                        audio=await audio.read(),
                        title=song_name[:256],
                        caption=f"🎵 {title}"[:1024],
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