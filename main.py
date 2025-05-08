import os
import re
import logging
import html
import importlib
import aiofiles
import time
import aiohttp
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Forbidden, TimedOut
import googleapiclient.discovery
import yt_dlp
import instaloader
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DEVELOPER_KEY = os.getenv("YOUTUBE_API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not DEVELOPER_KEY or not TOKEN:
    logger.error("YOUTUBE_API_KEY yoki TELEGRAM_TOKEN .env faylida topilmadi!")
    raise ValueError("API kalitlari yoki token sozlanmagan!")

try:
    youtube = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, developerKey=DEVELOPER_KEY, cache_discovery=False
    )
except Exception as e:
    logger.error(f"YouTube API ulanishda xato: {e}")
    raise

L = instaloader.Instaloader(
    max_connection_attempts=10,
    sleep=True,
    request_timeout=30,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def clean_title(title: str) -> str:
    if not title:
        return "Instagram Reel"

    title = html.unescape(title)

    patterns = [
        r'\s*\(Official Video\).*',
        r'\s*\[Official Video\].*',
        r'\s*\(Official Music Video\).*',
        r'\s*\[Official Music Video\].*',
        r'\s*\|.*$',
        r'\s*Video Clip.*$',
        r'\s*MV.*$',
        r'🎵.*$',
        r'\s*\(\s*\).*',
        r'\s*\[\s*\].*',
        r'\s*#[^\s]*',
    ]
    for pattern in patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    title = re.sub(r'\s+', ' ', title).strip()

    if not title:
        return "Instagram Reel"

    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist, song = "", title

    song = song.replace("'", "'")
    artist = artist.replace("'", "'")

    song = song[:256]
    full_title = f"{artist} - {song}" if artist else song
    full_title = full_title[:1024]

    logger.info(f"Tozalangan sarlavha: {full_title}")
    return full_title


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini yuboring (masalan: Hamdam Sobirov - Tentakcham) yoki YouTube/Instagram havolasini yuboring.\n"
        "Instagram havolalari uchun faqat video yuklanadi!"
    )


async def download_youtube_audio(video_id: str, filename: str) -> bool:
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
            'preferredquality': '128',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        for ext in ['webm', 'm4a', 'mp3']:
            path = f"{filename}.{ext}"
            if os.path.exists(path):
                os.rename(path, f"{filename}.mp3")
                file_size = os.path.getsize(f"{filename}.mp3") / (1024 * 1024)  # MB
                logger.info(f"Yuklangan MP3 fayl hajmi: {file_size:.2f} MB")
                return True
        return False
    except Exception as e:
        logger.error(f"YouTube audio yuklashda xato: {e}")
        return False


async def download_instagram_media(post_url: str, filename: str) -> tuple[bool, str, str]:
    try:
        shortcode = post_url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=filename)

        video_path = ""
        caption = post.caption or post.owner_username or "Instagram Reel"
        caption = clean_title(caption[:100])  # Uzun tavsiflarni qisqartirish

        files = os.listdir(filename)
        logger.info(f"Papkada topilgan fayllar: {files}")

        mp4_files = [f for f in files if f.endswith('.mp4')]
        if mp4_files:
            video_path = os.path.join(filename, mp4_files[0])
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            logger.info(f"Yuklangan MP4 fayl: {video_path}, hajmi: {file_size:.2f} MB")
            return True, video_path, caption

        jpg_files = [f for f in files if f.endswith('.jpg')]
        if jpg_files:
            logger.info(f"Rasm topildi: {jpg_files[0]}")
            return False, "", caption

        logger.error(f"Video fayli topilmadi, papka: {filename}")
        return False, "", caption
    except instaloader.exceptions.LoginRequiredException:
        logger.error("Instagram post maxfiy, login talab qilinadi")
        return False, "", "maxfiy post"
    except instaloader.exceptions.ConnectionException as e:
        logger.error(f"Instagram ulanish xatosi: {e}")
        return False, "", "ulanish xatosi"
    except Exception as e:
        logger.error(f"Instagram media yuklashda xato: {e}")
        return False, "", ""


async def search_youtube(query: str) -> tuple[str, str]:
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
    query_text = update.message.text
    await update.message.reply_text("🔎 Qidirilmoqda, biroz kuting...")

    is_youtube = "youtube.com" in query_text or "youtu.be" in query_text
    is_instagram = "instagram.com" in query_text
    filename = f"media_{uuid4().hex}"

    try:
        if is_youtube:
            video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", query_text)
            if not video_id:
                await update.message.reply_text("❌ Noto'g'ri YouTube havolasi!")
                return

            video_id = video_id.group(1)
            try:
                request = youtube.videos().list(part="snippet", id=video_id)
                response = request.execute()
                title = clean_title(response["items"][0]["snippet"]["title"]) if response.get("items") else query_text
            except Exception as e:
                logger.error(f"YouTube sarlavha olishda xato: {e}")
                title = query_text

            await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
            await process_youtube_download(update, video_id, filename, title)

        elif is_instagram:
            await update.message.reply_text("⬇️ Instagram'dan yuklanmoqda...")
            await process_instagram_download(update, query_text, filename)

        else:
            video_id, title = await search_youtube(query_text)
            if not video_id:
                await update.message.reply_text("❌ Hech narsa topilmadi. Boshqa so'rov yuborib ko'ring.")
                return

            await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
            await process_youtube_download(update, video_id, filename, title)

    except Exception as e:
        logger.error(f"Media qayta ishlashda xato: {e}")
        await update.message.reply_text("❌ Xato yuz berdi. Iltimos qayta urinib ko'ring.")

    finally:
        cleanup_files(filename)


async def process_youtube_download(update: Update, video_id: str, filename: str, title: str) -> None:
    if await download_youtube_audio(video_id, filename):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                    song_name = title.split(" - ")[-1] if " - " in title else title
                    await update.message.reply_audio(
                        audio=await audio.read(),
                        title=song_name[:256],
                        caption=f"🎵 {title}"[:1024],
                        filename=f"{title}.mp3"
                    )
                break
            except TimedOut as e:
                if attempt == max_retries - 1:
                    await update.message.reply_text("❌ Audio yuborishda xato yuz berdi (timeout).")
                else:
                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Audio yuborishda xato: {e}")
                await update.message.reply_text("❌ Audio yuborishda xato yuz berdi.")
                break
    else:
        await update.message.reply_text("❌ Audio yuklashda xato yuz berdi.")


async def process_instagram_download(update: Update, post_url: str, filename: str) -> None:
    success, video_path, title = await download_instagram_media(post_url, filename)

    if success and video_path.endswith('.mp4'):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiofiles.open(video_path, 'rb') as video:
                    await update.message.reply_video(
                        video=await video.read(),
                        caption=f"🎥 {title} (Instagram Video)"[:1024],
                        filename=f"{title}.mp4"
                    )
                break
            except TimedOut as e:
                if attempt == max_retries - 1:
                    await update.message.reply_text("❌ Video yuborishda xato yuz berdi (timeout).")
                else:
                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Video yuborishda xato: {e}")
                await update.message.reply_text("❌ Video yuborishda xato yuz berdi.")
                break
    else:
        if title == "maxfiy post":
            await update.message.reply_text("❌ Instagram post maxfiy, iltimos, jamoatchi reel havolasini yuboring.")
        elif title == "ulanish xatosi":
            await update.message.reply_text("❌ Instagram serveriga ulanishda xato, keyinroq urinib ko'ring.")
        elif video_path:
            await update.message.reply_text("❌ Bu Instagram posti rasm, video emas!")
        else:
            await update.message.reply_text("❌ Instagram'dan video yuklashda xato yuz berdi!")


def cleanup_files(filename: str) -> None:
    try:
        if os.path.exists(f"{filename}.mp3"):
            os.remove(f"{filename}.mp3")
        if os.path.exists(filename):
            for file in os.listdir(filename):
                os.remove(os.path.join(filename, file))
            os.rmdir(filename)
    except Exception as e:
        logger.error(f"Fayllarni tozalashda xato: {e}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Xato yuz berdi: {context.error}")

    if isinstance(context.error, Forbidden):
        logger.warning("Bot foydalanuvchi tomonidan bloklangan.")
        return

    if isinstance(context.error, TimedOut):
        logger.warning("Telegram API timeout xatosi.")
        return

    if update and update.message:
        try:
            await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko'ring.")
        except (Forbidden, TimedOut):
            pass
        except Exception as e:
            logger.error(f"Xato xabarini yuborishda xato: {e}")


def verify_dependencies() -> list:
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
                .get_updates_write_timeout(60)
                .get_updates_connect_timeout(30)
                .get_updates_pool_timeout(60)
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
