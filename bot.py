
import os
import re
import logging
import html
import aiofiles
import asyncio
from uuid import uuid4
from typing import Tuple, Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Forbidden, TimedOut, RetryAfter
import yt_dlp
import instaloader
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from aiohttp import web

# Configuration
load_dotenv()
CONFIG = {
    'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN'),
    'SPOTIFY_CLIENT_ID': os.getenv('SPOTIFY_CLIENT_ID'),
    'SPOTIFY_CLIENT_SECRET': os.getenv('SPOTIFY_CLIENT_SECRET'),
    'WEBHOOK_URL': os.getenv('WEBHOOK_URL'),  # e.g., https://your-domain.com
    'WEBHOOK_PORT': int(os.getenv('WEBHOOK_PORT', 8443)),
    'MP3_BITRATE': '96',
    'MAX_FILE_SIZE_MB': 20,
    'MAX_RETRIES': 3,
    'RETRY_DELAY': 2,
    'REQUEST_TIMEOUT': 60,
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
if not all([CONFIG['TELEGRAM_TOKEN'], CONFIG['SPOTIFY_CLIENT_ID'], CONFIG['SPOTIFY_CLIENT_SECRET'], CONFIG['WEBHOOK_URL']]):
    logger.error("Missing TELEGRAM_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, or WEBHOOK_URL in .env")
    raise ValueError("Required environment variables not configured")

# Spotify API client
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=CONFIG['SPOTIFY_CLIENT_ID'],
        client_secret=CONFIG['SPOTIFY_CLIENT_SECRET']
    ))
except Exception as e:
    logger.error(f"Failed to initialize Spotify API: {e}")
    raise

# Instaloader setup
instaloader_instance = instaloader.Instaloader(
    max_connection_attempts=10,
    sleep=True,
    request_timeout=CONFIG['INSTALOADER_TIMEOUT'],
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)

def clean_title(title: str) -> str:
    """Clean title for Telegram."""
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
        "Qo'shiq nomini (masalan: Hamdam Sobirov - Tentakcham) yoki Instagram havolasini yuboring."
    )

async def download_youtube_audio(query: str, filename: str) -> Tuple[bool, str]:
    """Download audio from YouTube using search query."""
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
            ydl.download([f"ytsearch:{query}"])
        for ext in CONFIG['ALLOWED_EXTENSIONS']:
            path = f"{filename}.{ext}"
            if os.path.exists(path):
                os.rename(path, f"{filename}.mp3")
                file_size = os.path.getsize(f"{filename}.mp3") / (1024 * 1024)
                logger.info(f"Downloaded MP3 size: {file_size:.2f} MB")
                if file_size > CONFIG['MAX_FILE_SIZE_MB']:
                    logger.info("Compressing oversized file...")
                    subprocess.run([
                        'ffmpeg', '-i', f"{filename}.mp3", '-b:a', '64k', f"{filename}_compressed.mp3"
                    ], check=True)
                    os.remove(f"{filename}.mp3")
                    os.rename(f"{filename}_compressed.mp3", f"{filename}.mp3")
                    file_size = os.path.getsize(f"{filename}.mp3") / (1024 * 1024)
                    logger.info(f"Compressed MP3 size: {file_size:.2f} MB")
                return True, query
        return False, ""
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return False, ""

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

async def search_spotify(query: str) -> Tuple[str, str]:
    """Search Spotify for a song."""
    try:
        results = sp.search(q=query, type='track', limit=1)
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            artist = track['artists'][0]['name']
            title = track['name']
            full_title = f"{artist} - {title}"
            return clean_title(full_title), f"{artist} {title}"
        return "", ""
    except Exception as e:
        logger.error(f"Spotify search error: {e}")
        return "", ""

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user media request."""
    query = update.message.text
    filename = f"media_{uuid4().hex}"

    try:
        await update.message.reply_text("🔎 Qidirilmoqda...")

        if "instagram.com" in query:
            await update.message.reply_text("⬇️ Instagram'dan yuklanmoqda...")
            await process_instagram_download(update, query, filename)
        else:
            title, youtube_query = await search_spotify(query)
            if not title:
                await update.message.reply_text("❌ Nothing found. Try another query.")
                return
            await update.message.reply_text(f"⬇️ Yuklanmoqda: {title}")
            await process_youtube_download(update, youtube_query, filename, title)

    except Exception as e:
        logger.error(f"Media processing error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

    finally:
        cleanup_files(filename)

async def process_youtube_download(update: Update, youtube_query: str, filename: str, title: str) -> None:
    """Handle YouTube audio download and upload."""
    success, _ = await download_youtube_audio(youtube_query, filename)
    if success:
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

async def webhook_handler(request: web.Request) -> web.Response:
    """Handle incoming Telegram webhook updates."""
    logger.info("Received webhook request from Telegram")
    try:
        data = await request.json()
        logger.info(f"Webhook data received: {data}")
        update = Update.de_json(data, application.bot)
        if update:
            logger.info(f"Processing update: {update}")
            await application.process_update(update)
        else:
            logger.warning("No valid update received in webhook")
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        return web.Response(status=500)

async def setup_webhook(app: Application) -> None:
    """Set up Telegram webhook."""
    try:
        await app.bot.set_webhook(
            url=f"{CONFIG['WEBHOOK_URL']}/telegram",
            allowed_updates=Update.ALL_TYPES
        )
        logger.info(f"Webhook set to {CONFIG['WEBHOOK_URL']}/telegram")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        raise

async def start_webhook_server(app: Application) -> None:
    web_app = web.Application()
    web_app.router.add_post('/telegram', webhook_handler)  # Endpoint /telegram

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', CONFIG['WEBHOOK_PORT'])
    await site.start()

    logger.info(f"Starting webhook server on port {CONFIG['WEBHOOK_PORT']}")
    await asyncio.Event().wait()

async def main() -> None:
    """Run the bot with webhook."""
    global application
    application = (
        Application.builder()
        .token(CONFIG['TELEGRAM_TOKEN'])
        .read_timeout(CONFIG['REQUEST_TIMEOUT'])
        .write_timeout(CONFIG['REQUEST_TIMEOUT'])
        .connect_timeout(30)
        .pool_timeout(60)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_media))
    application.add_error_handler(error_handler)

    await setup_webhook(application)
    await start_webhook_server(application)

if __name__ == "__main__":
    asyncio.run(main())