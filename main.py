import os
import re
import logging
import html
import importlib
import aiofiles
import asyncio
import time
from uuid import uuid4
from dotenv import load_dotenv
import googleapiclient.discovery
import googleapiclient.errors
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Forbidden, TimedOut
import structlog
from cachetools import TTLCache

# Environment variables
load_dotenv()

# Logging setup
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# Check environment variables
required_env_vars = ["YOUTUBE_API_KEY", "TELEGRAM_TOKEN"]
for var in required_env_vars:
    if not os.getenv(var):
        logger.error(f"Environment variable missing", variable=var)
        raise ValueError(f"{var} is not set in .env file")

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DEVELOPER_KEY = os.getenv("YOUTUBE_API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")
COOKIES_PATH = os.getenv("COOKIES_PATH", "cookies.txt")

# Rate limit cache
user_requests = TTLCache(maxsize=1000, ttl=60)  # 1 min TTL, max 5 requests per user

# YouTube API setup
try:
    youtube = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, developerKey=DEVELOPER_KEY, cache_discovery=False
    )
except Exception as e:
    logger.error("Failed to initialize YouTube API", error=str(e))
    raise

def clean_title(title: str) -> str:
    if not title:
        return "Unknown Song"

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
        return "Unknown Song"

    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist, song = "", title

    song = song.replace("'", "'")
    artist = artist.replace("'", "'")

    song = song[:256]
    full_title = f"{artist} - {song}" if artist else song
    full_title = full_title[:1024]

    logger.info("Cleaned title", title=full_title)
    return full_title

def is_valid_url(url: str) -> bool:
    pattern = r'^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.*$'
    return bool(re.match(pattern, url))

def parse_query(query: str) -> tuple[str, str]:
    query = query.strip()
    if " - " in query:
        artist, song = query.split(" - ", 1)
        return artist.strip(), song.strip()
    words = query.split()
    if len(words) >= 2:
        artist = words[0]
        song = " ".join(words[1:])
        return artist.strip(), song.strip()
    return "", query.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo‘shiqchi ismi va qo‘shiq nomini kiriting (masalan: Hamdam Sobirov - Tentakcham) yoki YouTube havolasini yuboring."
    )

async def download_youtube_audio(video_id: str, filename: str) -> bool:
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = f"{filename}.mp3"

    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        if file_size > 0 and file_size <= 50:
            logger.info("MP3 file already exists, skipping download", path=output_path, size=file_size)
            return True
        else:
            logger.warning("Existing file is invalid, removing", path=output_path)
            os.remove(output_path)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'cookies': COOKIES_PATH,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'max_duration': 600,
        'noplaylist': True,
        'nooverwrites': True,
    }

    try:
        loop = asyncio.get_event_loop()
        async with asyncio.timeout(300):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])

        for ext in ['webm', 'm4a', 'mp3']:
            temp_path = f"{filename}.{ext}"
            if os.path.exists(temp_path):
                os.rename(temp_path, output_path)
                file_size = os.path.getsize(output_path) / (1024 * 1024)
                if file_size > 50:
                    logger.warning("File size exceeds Telegram limit", size=file_size)
                    os.remove(output_path)
                    return False
                logger.info("Downloaded and renamed MP3 file", path=output_path, size=file_size)
                return True
        logger.error("No audio file found after download")
        return False
    except asyncio.TimeoutError:
        logger.error("YouTube download timed out")
        return False
    except Exception as e:
        logger.error("YouTube download failed", error=str(e))
        return False

async def search_youtube(artist: str, song: str) -> tuple[str, str]:
    query = f"{artist} {song}" if artist else song
    for attempt in range(3):
        try:
            request = youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=5
            )
            response = request.execute()
            if response.get("items"):
                for item in response["items"]:
                    raw_title = item["snippet"]["title"]
                    title = clean_title(raw_title).lower()
                    if artist and song:
                        if artist.lower() in title and song.lower() in title:
                            logger.info("YouTube matched title", title=raw_title)
                            return item["id"]["videoId"], clean_title(raw_title)
                    elif song.lower() in title:
                        logger.info("YouTube matched title", title=raw_title)
                        return item["id"]["videoId"], clean_title(raw_title)
            return "", ""
        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 429:
                await asyncio.sleep(2 ** attempt)
                continue
            logger.error("YouTube API error", error=str(e))
            return "", ""
        except Exception as e:
            logger.error("YouTube search failed", error=str(e))
            return "", ""
    logger.error("YouTube search retries exhausted")
    return "", ""

async def send_file(update: Update, file_path: str, title: str) -> bool:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with aiofiles.open(file_path, 'rb') as file:
                song_name = title.split(" - ")[-1] if " - " in title else title
                await update.message.reply_audio(
                    audio=await file.read(),
                    title=song_name[:256],
                    caption=f"🎵 {title}"[:1024],
                    filename=f"{title}.mp3"
                )
            return True
        except TimedOut:
            if attempt == max_retries - 1:
                await update.message.reply_text("❌ Fayl yuborishda xato (timeout).")
                return False
            await asyncio.sleep(2 ** (attempt + 1))
        except Exception as e:
            logger.error("File sending failed", error=str(e))
            await update.message.reply_text("❌ Fayl yuborishda xato yuz berdi.")
            return False
    return False

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_requests.get(user_id, 0) >= 5:
        await update.message.reply_text("❌ So'rovlar chegarasi! Bir daqiqa kuting.")
        return
    user_requests[user_id] = user_requests.get(user_id, 0) + 1

    query_text = update.message.text
    msg = await update.message.reply_text("🔎 Qidirilmoqda...")

    is_youtube = "youtube.com" in query_text or "youtu.be" in query_text
    filename = f"media_{uuid4().hex}"

    try:
        async with asyncio.timeout(600):
            if is_youtube:
                if not is_valid_url(query_text):
                    await msg.edit_text("❌ Noto'g'ri YouTube havolasi!")
                    return
                video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", query_text)
                if not video_id:
                    await msg.edit_text("❌ Noto'g'ri YouTube havolasi!")
                    return

                video_id = video_id.group(1)
                try:
                    request = youtube.videos().list(part="snippet", id=video_id)
                    response = request.execute()
                    title = clean_title(response["items"][0]["snippet"]["title"]) if response.get("items") else query_text
                except Exception as e:
                    logger.error("YouTube title fetch failed", error=str(e))
                    title = query_text

                await msg.edit_text(f"⬇️ Yuklanmoqda: {title}")
                await process_youtube_download(update, msg, video_id, filename, title)

            else:
                artist, song = parse_query(query_text)
                if not song:
                    await msg.edit_text("❌ Qo‘shiq nomini kiriting!")
                    return
                video_id, title = await search_youtube(artist, song)
                if not video_id:
                    await msg.edit_text("❌ Hech narsa topilmadi. Artist va qo‘shiq nomini to‘g‘ri kiriting.")
                    return

                await msg.edit_text(f"⬇️ Yuklanmoqda: {title}")
                await process_youtube_download(update, msg, video_id, filename, title)

    except asyncio.TimeoutError:
        logger.error("Media processing timed out")
        await msg.edit_text("❌ Vaqt tugadi, iltimos qayta urinib ko'ring.")
    except Exception as e:
        logger.error("Media processing failed", error=str(e), exc_info=True)
        await msg.edit_text("❌ Xato yuz berdi. Iltimos qayta urinib ko'ring.")
    finally:
        await cleanup_files(filename)

async def process_youtube_download(update: Update, msg, video_id: str, filename: str, title: str) -> None:
    if await download_youtube_audio(video_id, filename):
        await send_file(update, f"{filename}.mp3", title)
    else:
        await msg.edit_text("❌ Audio yuklashda xato yuz berdi.")

async def cleanup_files(filename: str) -> None:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            mp3_path = f"{filename}.mp3"
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
                logger.info("Removed MP3 file", path=mp3_path)

            if os.path.exists(filename):
                for file in os.listdir(filename):
                    file_path = os.path.join(filename, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logger.info("Removed temporary file", path=file_path)
                os.rmdir(filename)
                logger.info("Removed temporary directory", path=filename)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error("File cleanup failed after retries", error=str(e))
            else:
                logger.warning("Cleanup attempt failed, retrying", attempt=attempt + 1)
                await asyncio.sleep(1)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Bot error", error=str(context.error))
    if isinstance(context.error, Forbidden):
        logger.warning("Bot blocked by user")
        return
    if isinstance(context.error, TimedOut):
        logger.warning("Telegram API timeout")
        return
    if update and update.message:
        try:
            await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko'ring.")
        except (Forbidden, TimedOut):
            pass
        except Exception as e:
            logger.error("Error message sending failed", error=str(e))

def verify_dependencies() -> list:
    required_packages = [
        ('python-telegram-bot', 'telegram'),
        ('google-api-python-client', 'googleapiclient'),
        ('yt-dlp', 'yt_dlp'),
        ('aiofiles', 'aiofiles'),
        ('python-dotenv', 'dotenv'),
        ('structlog', 'structlog'),
        ('cachetools', 'cachetools'),
    ]
    missing = []
    for package, module in required_packages:
        try:
            importlib.import_module(module)
            logger.info(f"Dependency found", package=package, module=module)
        except ImportError as e:
            logger.error(f"Dependency missing", package=package, module=module, error=str(e))
            missing.append(package)
    return missing

def main() -> None:
    missing_packages = verify_dependencies()
    if missing_packages:
        logger.error("Missing dependencies", packages=missing_packages)
        logger.error("Install them with: pip install -r requirements.txt")
        return

    max_retries = 3
    retry_count = 0
    retry_delay = 5
    while retry_count < max_retries:
        try:
            logger.info("Initializing Telegram bot application")
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
            logger.info("Bot started successfully")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
            break
        except TimeoutError as e:
            retry_count += 1
            logger.error(f"Timeout error ({retry_count}/{max_retries})", error=str(e))
            if retry_count < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds")
                time.sleep(retry_delay)
            else:
                logger.error("Max retries exhausted")
        except Exception as e:
            logger.error("Bot startup failed", error=str(e), exc_info=True)
            break

if __name__ == "__main__":
    main()