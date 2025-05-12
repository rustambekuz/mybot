
import os
import re
import logging
import html
import importlib
import aiofiles
import asyncio
import subprocess
from uuid import uuid4
from typing import Tuple, Optional
from telegram import Update, __version__ as TELEGRAM_VERSION
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Forbidden, TimedOut, RetryAfter
import googleapiclient.discovery
import yt_dlp
import instaloader
from dotenv import load_dotenv

# Configuration
load_dotenv()
CONFIG = {
    'YOUTUBE_API_KEY': os.getenv('YOUTUBE_API_KEY'),
    'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN'),
    'API_SERVICE_NAME': 'youtube',
    'API_VERSION': 'v3',
    'MP3_BITRATE': '96',  # Lowered for smaller files
    'MAX_FILE_SIZE_MB': 20,  # Threshold for compression
    'MAX_RETRIES': 3,
    'RETRY_DELAY': 2,
    'REQUEST_TIMEOUT': 60,  # Used for Application-level timeouts
    'INSTALOADER_TIMEOUT': 30,
    'ALLOWED_EXTENSIONS': ['webm', 'm4a', 'mp3'],
}

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Validate environment variables
if not all([CONFIG['YOUTUBE_API_KEY'], CONFIG['TELEGRAM_TOKEN']]):
    logger.error("Missing YOUTUBE_API_KEY or TELEGRAM_TOKEN in .env file")
    raise ValueError("API keys or token not configured")

# YouTube API client
try:
    youtube = googleapiclient.discovery.build(
        CONFIG['API_SERVICE_NAME'], CONFIG['API_VERSION'],
        developerKey=CONFIG['YOUTUBE_API_KEY'], cache_discovery=False
    )
except Exception as e:
    logger.error(f"Failed to initialize YouTube API: {e}")
    raise

# Instaloader setup
instaloader_instance = instaloader.Instaloader(
    max_connection_attempts=10,
    sleep=True,
    request_timeout=CONFIG['INSTALOADER_TIMEOUT'],
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)

def clean_title(title: str) -> str:
    """Clean YouTube or Instagram title for Telegram."""
    if not title:
        return "Media"

    title = html.unescape(title)
    patterns = [
        r'\s*\(Official (Music )?Video\).*',
        r'\s*\[Official (Music )?Video\].*',
        r'\s*\|.*$', r'\s*Video Clip.*$', r'\s*MV.*$',
        r'🎵.*$', r'\s*\(\s*\).*', r'\s*\[\s*\].*', r'\s*#[^\s]*'
    ]
    for pattern in patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    title = re.sub(r'\s+', ' ', title).strip() or "Media"
    artist, song = (title.split(" - ", 1) if " - " in title else ("", title))
    song = song.replace("'", "'")[:256]
    artist = artist.replace("'", "'")
    full_title = f"{artist} - {song}" if artist else song
    return full_title[:1024]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini (masalan: Hamdam Sobirov - Tentakcham) yoki YouTube/Instagram havolasini yuboring."
    )

async def download_youtube_audio(video_id: str, filename: str) -> bool:
    """Download audio from YouTube and optimize file size."""
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': CONFIG['MP3_BITRATE'],
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        for ext in CONFIG['ALLOWED_EXTENSIONS']:
            path = f"{filename}.{ext}"
            if os.path.exists(path):
                os.rename(path, f"{filename}.mp3")
                file_size = os.path.getsize(f"{filename}.mp3") / (1024 * 1024)
                logger.info(f"Downloaded MP3 size: {file_size:.2f} MB")

                if file_size > CONFIG['MAX_FILE_SIZE_MB']:
                    logger.info("Compressing oversized file...")
                    new_filename = f"{filename}_compressed.mp3"
                    subprocess.run([
                        'ffmpeg', '-i', f"{filename}.mp3", '-b:a', '64k', new_filename
                    ], check=True)
                    os.remove(f"{filename}.mp3")
                    os.rename(new_filename, f"{filename}.mp3")
                    file_size = os.path.getsize(f"{filename}.mp3") / (1024 * 1024)
                    logger.info(f"Compressed MP3 size: {file_size:.2f} MB")
                return True
        return False
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return False

async def download_instagram_media(post_url: str, filename: str) -> Tuple[bool, str, str]:
    """Download video from Instagram."""
    try:
        shortcode = post_url.split("/")[-2]
        post = instaloader.Post.from_shortcode(instaloader_instance.context, shortcode)
        instaloader_instance.download_post(post, target=filename)

        caption = clean_title(post.caption or post.owner_username or "Instagram Reel")[:100]
        files = os.listdir(filename)
        mp4_files = [f for f in files if f.endswith('.mp4')]

        if mp4_files:
            video_path = os.path.join(filename, mp4_files[0])
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            logger.info(f"Downloaded MP4: {video_path}, size: {file_size:.2f} MB")
            return True, video_path, caption
        logger.error(f"No video found in {filename}")
        return False, "", caption
    except instaloader.exceptions.LoginRequiredException:
        logger.error("Private Instagram post detected")
        return False, "", "private post"
    except instaloader.exceptions.ConnectionException as e:
        logger.error(f"Instagram connection error: {e}")
        return False, "", "connection error"
    except Exception as e:
        logger.error(f"Instagram download error: {e}")
        return False, "", ""

async def search_youtube(query: str) -> Tuple[str, str]:
    """Search YouTube for a song."""
    try:
        request = youtube.search().list(part="snippet", q=query, type="video", maxResults=1)
        response = request.execute()
        if response.get("items"):
            item = response["items"][0]
            return item["id"]["videoId"], clean_title(item["snippet"]["title"])
        return "", ""
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return "", ""

async def get_youtube_title(video_id: str) -> str:
    """Fetch YouTube video title."""
    try:
        request = youtube.videos().list(part="snippet", id=video_id)
        response = request.execute()
        return clean_title(response["items"][0]["snippet"]["title"]) if response.get("items") else "Unknown Title"
    except Exception as e:
        logger.error(f"YouTube title fetch error: {e}")
        return "Unknown Title"

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user media request."""
    query = update.message.text
    filename = f"media_{uuid4().hex}"

    try:
        await update.message.reply_text("🔎 Qidirilmoqda...")

        if "youtube.com" in query or "youtu.be" in query:
            video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", query)
            if not video_id:
                await update.message.reply_text("❌ Invalid YouTube link!")
                return
            video_id = video_id.group(1)
            title = await get_youtube_title(video_id)
            await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
            await process_youtube_download(update, video_id, filename, title)

        elif "instagram.com" in query:
            await update.message.reply_text("⬇️ Instagram'dan yuklanmoqda...")
            await process_instagram_download(update, query, filename)

        else:
            video_id, title = await search_youtube(query)
            if not video_id:
                await update.message.reply_text("❌ Nothing found. Try another query.")
                return
            await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
            await process_youtube_download(update, video_id, filename, title)

    except Exception as e:
        logger.error(f"Media processing error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

    finally:
        cleanup_files(filename)

async def process_youtube_download(update: Update, video_id: str, filename: str, title: str) -> None:
    """Handle YouTube audio download and upload."""
    if await download_youtube_audio(video_id, filename):
        for attempt in range(CONFIG['MAX_RETRIES']):
            try:
                async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                    song_name = title.split(" - ")[-1] if " - " in title else title
                    await update.message.reply_audio(
                        audio=await audio.read(),
                        title=song_name[:256],
                        caption=f"🎵 {title}"[:1024],
                        filename=f"{title}.mp3"
                    )
                return
            except RetryAfter as e:
                logger.warning(f"Flood control: waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after + 1)
            except TimedOut:
                if attempt == CONFIG['MAX_RETRIES'] - 1:
                    await update.message.reply_text("❌ Audio upload timed out.")
                else:
                    await asyncio.sleep(CONFIG['RETRY_DELAY'])
            except Exception as e:
                logger.error(f"Audio upload error: {e}")
                await update.message.reply_text("❌ Failed to send audio.")
                return
    else:
        await update.message.reply_text("❌ Failed to download audio.")

async def process_instagram_download(update: Update, post_url: str, filename: str) -> None:
    """Handle Instagram video download and upload."""
    success, video_path, caption = await download_instagram_media(post_url, filename)

    if success and video_path.endswith('.mp4'):
        for attempt in range(CONFIG['MAX_RETRIES']):
            try:
                async with aiofiles.open(video_path, 'rb') as video:
                    await update.message.reply_video(
                        video=await video.read(),
                        caption=f"🎥 {caption} (Instagram)"[:1024],
                        filename=f"{caption}.mp4"
                    )
                return
            except RetryAfter as e:
                logger.warning(f"Flood control: waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after + 1)
            except TimedOut:
                if attempt == CONFIG['MAX_RETRIES'] - 1:
                    await update.message.reply_text("❌ Video upload timed out.")
                else:
                    await asyncio.sleep(CONFIG['RETRY_DELAY'])
            except Exception as e:
                logger.error(f"Video upload error: {e}")
                await update.message.reply_text("❌ Failed to send video.")
                return
    else:
        error_messages = {
            "private post": "❌ Private Instagram post, please use a public reel link.",
            "connection error": "❌ Instagram server connection error, try again later."
        }
        await update.message.reply_text(error_messages.get(caption, "❌ Failed to download Instagram video."))

def cleanup_files(filename: str) -> None:
    """Clean up temporary files."""
    try:
        if os.path.exists(f"{filename}.mp3"):
            os.remove(f"{filename}.mp3")
        if os.path.exists(filename):
            for file in os.listdir(filename):
                os.remove(os.path.join(filename, file))
            os.rmdir(filename)
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle bot errors."""
    logger.error(f"Error occurred: {context.error}")

    if isinstance(context.error, Forbidden):
        logger.warning("Bot blocked by user.")
        return
    if isinstance(context.error, TimedOut):
        logger.warning("Telegram API timeout.")
        if update and update.message:
            await update.message.reply_text("⌛ Connection delay, retrying...")
            await asyncio.sleep(CONFIG['RETRY_DELAY'])
            await process_media(update, context)
        return
    if update and update.message:
        await update.message.reply_text("❌ Bot error. Please try again later.")

def verify_dependencies() -> list:
    """Check for required dependencies and library version."""
    required = [
        ('python-telegram-bot', 'telegram'),
        ('google-api-python-client', 'googleapiclient'),
        ('yt-dlp', 'yt_dlp'),
        ('instaloader', 'instaloader'),
        ('aiofiles', 'aiofiles'),
        ('python-dotenv', 'dotenv')
    ]
    missing = []
    for pkg, mod in required:
        try:
            importlib.import_module(mod)
        except ImportError as e:
            logger.error(f"Missing {pkg}: {e}")
            missing.append(pkg)

    # Check python-telegram-bot version
    if TELEGRAM_VERSION < "20.0":
        logger.warning(
            f"python-telegram-bot version {TELEGRAM_VERSION} detected. "
            "Consider upgrading to v20.0+ for better timeout control: pip install python-telegram-bot --upgrade"
        )

    return missing

def main() -> None:
    """Run the bot."""
    if missing := verify_dependencies():
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.error("Install them with: pip install -r requirements.txt")
        return

    for attempt in range(CONFIG['MAX_RETRIES']):
        try:
            application = (
                Application.builder()
                .token(CONFIG['TELEGRAM_TOKEN'])
                .read_timeout(CONFIG['REQUEST_TIMEOUT'])
                .write_timeout(CONFIG['REQUEST_TIMEOUT'])
                .connect_timeout(30)
                .pool_timeout(60)
                .get_updates_read_timeout(CONFIG['REQUEST_TIMEOUT'])
                .get_updates_write_timeout(CONFIG['REQUEST_TIMEOUT'])
                .get_updates_connect_timeout(30)
                .get_updates_pool_timeout(60)
                .build()
            )

            application.add_handler(CommandHandler("start", start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_media))
            application.add_error_handler(error_handler)

            logger.info("Bot started...")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
            return

        except TimeoutError as e:
            logger.error(f"Timeout error ({attempt + 1}/{CONFIG['MAX_RETRIES']}): {e}")
            if attempt < CONFIG['MAX_RETRIES'] - 1:
                logger.info(f"Retrying in {CONFIG['RETRY_DELAY']}s...")
                time.sleep(CONFIG['RETRY_DELAY'])
        except Exception as e:
            logger.error(f"Startup error: {e}")
            return

if __name__ == "__main__":
    main()
