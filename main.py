import os
import re
import logging
import html
import aiofiles
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, ContentTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import googleapiclient.discovery
import yt_dlp
from uuid import uuid4
import signal
import psutil

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# YouTube API configuration
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DEVELOPER_KEY = "AIzaSyBpGD78aAuu69-GhK8VHcdhs9PSqNzWaVM"
youtube = googleapiclient.discovery.build(
    API_SERVICE_NAME, API_VERSION, developerKey=DEVELOPER_KEY, cache_discovery=False
)

# Telegram bot token
TOKEN = "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4"

# State management
class MusicSearch(StatesGroup):
    searching = State()

def clean_title(title: str) -> tuple[str, str]:
    """Clean YouTube video title and separate artist and song name"""
    title = html.unescape(title).replace("'", "'")

    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist, song = "", title

    song = re.sub(r'\s*\|.*$', '', song)
    song = re.sub(r'\s*Video Clip.*$', '', song, flags=re.IGNORECASE)
    song = re.sub(r'■.*$', '', song)
    song = re.sub(r'\s*\[.*?\]', '', song)
    song = re.sub(r'\s+', ' ', song).strip()

    artist = re.sub(r'\s+', ' ', artist).strip()

    if not song and artist:
        song = artist
        artist = ""

    return artist, song

def format_filename(title: str) -> str:
    """Clean special characters and spaces for filename"""
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'\s+', '_', title).strip()
    return title[:50]

async def download_audio(video_id: str, filename: str) -> bool:
    """Download audio from YouTube video"""
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
        logger.error(f"Error downloading audio: {e}")
        return False

def terminate_other_instances() -> None:
    """Terminate other running bot instances"""
    current_pid = os.getpid()
    bot_token = TOKEN.split(':')[0]
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.cmdline())
            if (proc.pid != current_pid and
                    'python' in proc.name().lower() and
                    bot_token in cmdline):
                logger.info(f"Found old bot process (PID: {proc.pid}), terminating...")
                try:
                    proc.send_signal(signal.SIGTERM)
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    logger.warning(f"Process (PID: {proc.pid}) didn't terminate, sending SIGKILL...")
                    proc.send_signal(signal.SIGKILL)
                    proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            logger.warning(f"Error terminating process (PID: {proc.pid}): {e}")
            continue

async def clear_webhook(bot: Bot) -> None:
    """Clear webhook before starting bot"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook successfully cleared.")
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Webhook status: {webhook_info}")
    except Exception as e:
        logger.error(f"Error clearing webhook: {e}")

# Bot initialization
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)

@dp.message(CommandStart())
async def start_command(message: types.Message):
    """Handle /start command"""
    await message.answer(
        f"Salom, {message.from_user.first_name}!\n"
        "Qo'shiq nomini yuboring, masalan: Hamdam Sobirov - Tentakcham\n"
        "Iltimos, qo'shiqchi ismini to'g'ri yozing!"
    )

@dp.message(ContentTypeFilter(content_types=[types.ContentType.TEXT]))
async def search_music(message: types.Message, state: FSMContext):
    """Search and send music based on user query"""
    query_text = message.text
    await message.answer("🔎 Qidirilmoqda, biroz kuting...")
    await state.set_state(MusicSearch.searching)

    try:
        request = youtube.search().list(
            part="snippet",
            q=query_text,
            type="video",
            maxResults=1
        )
        response = request.execute()
    except Exception as e:
        logger.error(f"YouTube API error: {e}")
        await message.answer("❌ YouTube API bilan muammo yuz berdi. Keyinroq urinib ko'ring.")
        await state.clear()
        return

    if not response.get("items"):
        await message.answer("❌ Hech narsa topilmadi. Boshqa so'rov yuborib ko'ring.")
        await state.clear()
        return

    item = response["items"][0]
    video_id = item["id"]["videoId"]
    raw_title = item["snippet"]["title"]
    artist, song = clean_title(raw_title)

    full_title = f"{artist} - {song}" if artist else song
    logger.info(f"Cleaned title: {full_title}")

    await message.answer(f"⬇️ Yuklanmoqda: {full_title}")

    filename = f"audio_{uuid4().hex}"
    formatted_filename = format_filename(full_title)

    if await download_audio(video_id, filename):
        try:
            async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                await message.answer_audio(
                    audio=await audio.read(),
                    title=song,
                    performer=artist if artist else None,
                    caption=f"🎵 {full_title}",
                    filename=f"{formatted_filename}.mp3"
                )
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            await message.answer("❌ Audio yuborishda xato yuz berdi.")
        finally:
            if os.path.exists(f"{filename}.mp3"):
                os.remove(f"{filename}.mp3")
    else:
        await message.answer("❌ Audio yuklashda xato yuz berdi.")

    await state.clear()

@dp.errors()
async def error_handler(update: types.Update, exception: Exception):
    """Handle errors and notify user"""
    logger.error(f"Error occurred: {exception}")
    if str(exception).startswith("Conflict: terminated by other getUpdates request"):
        logger.warning("Multiple bot instances detected.")
        if update.message:
            await update.message.answer(
                "❌ Botda muammo: Bir nechta bot instansiyasi ishlamoqda. "
                "Iltimos, serverda faqat bitta bot jarayoni ishlashiga ishonch hosil qiling."
            )
    elif isinstance(exception, asyncio.CancelledError):
        logger.warning("asyncio.CancelledError detected.")
    elif update.message:
        await update.message.answer("❌ Botda muammo yuz berdi. Keyinroq urinib ko'ring.")
    return True

async def main():
    """Start the bot"""
    try:
        logger.info("Cleaning up old bot processes...")
        terminate_other_instances()

        await clear_webhook(bot)

        logger.info("Bot starting...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=True
        )
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
    finally:
        logger.info("Bot shutting down...")
        await bot.session.close()
        await storage.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Event loop error: {e}")
        raise