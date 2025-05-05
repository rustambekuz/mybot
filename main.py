import os
import re
import logging
import html
import aiofiles
import asyncio
import signal
import psutil
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import googleapiclient.discovery
import yt_dlp
from uuid import uuid4

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# YouTube API sozlamalari
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DEVELOPER_KEY = "AIzaSyBpGD78aAuu69-GhK8VHcdhs9PSqNzWaVM"
youtube = googleapiclient.discovery.build(
    API_SERVICE_NAME, API_VERSION, developerKey=DEVELOPER_KEY, cache_discovery=False
)

# Telegram bot tokeni
TOKEN = "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4"

def clean_title(title: str) -> tuple[str, str]:
    """YouTube video sarlavhasini tozalash va artist bilan qo'shiq nomini ajratish"""
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
    """Fayl nomi uchun maxsus belgilar va bo'shliqlarni tozalash"""
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'\s+', '_', title).strip()
    return title[:50]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushirish uchun /start buyrug'i"""
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini yuboring, masalan: Hamdam Sobirov - Tentakcham\n"
        "Iltimos, qo'shiqchi ismini to'g'ri yozing!"
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
    raw_title = item["snippet"]["title"]
    artist, song = clean_title(raw_title)

    full_title = f"{artist} - {song}" if artist else song
    logger.info(f"Tozalangan sarlavha: {full_title}")

    await update.message.reply_text(f"⬇️ Yuklanmoqda: {full_title}")

    filename = f"audio_{uuid4().hex}"
    formatted_filename = format_filename(full_title)

    if await download_audio(video_id, filename):
        try:
            async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                await update.message.reply_audio(
                    audio=await audio.read(),
                    title=song,
                    performer=artist if artist else None,
                    caption=f"🎵 {full_title}",
                    filename=f"{formatted_filename}.mp3"
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
    if str(context.error).startswith("Conflict: terminated by other getUpdates request"):
        logger.warning("Bir nechta bot instansiyasi aniqlandi. Faqat bitta instansiya ishlashi kerak.")
        if update and update.message:
            await update.message.reply_text(
                "❌ Botda muammo: Bir nechta bot instansiyasi ishlamoqda. "
                "Iltimos, serverda faqat bitta bot jarayoni ishlashiga ishonch hosil qiling."
            )
    elif str(context.error).startswith("asyncio.CancelledError"):
        logger.warning("asyncio.CancelledError aniqlandi, bu Application.stop orqali yopilgan bo'lishi mumkin.")
    elif update and update.message:
        await update.message.reply_text("❌ Botda muammo yuz berdi. Keyinroq urinib ko'ring.")

async def clear_webhook(application: Application) -> None:
    """Bot ishga tushishdan oldin webhookni o'chirish"""
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook muvaffaqiyatli o'chirildi.")
        # Qo'shimcha tasdiqlash uchun getWebhookInfo
        webhook_info = await application.bot.get_webhook_info()
        logger.info(f"Webhook holati: {webhook_info}")
    except Exception as e:
        logger.error(f"Webhook o'chirishda xato: {e}")

def terminate_other_instances() -> None:
    """Boshqa bot jarayonlarini to'xtatish"""
    current_pid = os.getpid()
    bot_token = TOKEN.split(':')[0]  # Tokenning birinchi qismi (bot ID)
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.cmdline())
            # Bot jarayonini aniqlash uchun token va fayl nomini tekshirish
            if (proc.pid != current_pid and
                    'python' in proc.name().lower() and
                    bot_token in cmdline):
                logger.info(f"Eski bot jarayoni aniqlandi (PID: {proc.pid}, cmdline: {cmdline}), to'xtatilmoqda...")
                try:
                    proc.send_signal(signal.SIGTERM)
                    proc.wait(timeout=5)  # Jarayon to'xtashini 5 soniya kutish
                except psutil.TimeoutExpired:
                    logger.warning(f"Jarayon (PID: {proc.pid}) SIGTERM bilan to'xtamadi, SIGKILL yuborilmoqda...")
                    proc.send_signal(signal.SIGKILL)
                    proc.wait(timeout=3)  # SIGKILLdan keyin 3 soniya kutish
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            logger.warning(f"Jarayon to'xtatishda xato (PID: {proc.pid}): {e}")
            continue

async def main() -> None:
    """Botni ishga tushirish"""
    try:
        # Eski jarayonlarni tozalash
        logger.info("Eski bot jarayonlarini tozalash...")
        terminate_other_instances()

        # Application yaratish
        application = Application.builder().token(TOKEN).build()

        # Webhookni o'chirish
        await clear_webhook(application)

        # Handler'larni qo'shish
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
        application.add_error_handler(error_handler)

        logger.info("Bot ishga tushdi...")

        # Pollingni boshlash
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=10
        )

        # Botni to'xtatishni kutish
        while True:
            await asyncio.sleep(3600)  # Bot doimiy ishlashi uchun

    except Exception as e:
        logger.error(f"Botni ishga tushirishda xato: {e}")
        raise
    finally:
        # Botni to'g'ri to'xtatish
        if 'application' in locals():
            logger.info("Bot to'xtatilmoqda...")
            await application.stop()
            await application.shutdown()
            logger.info("Bot muvaffaqiyatli to'xtatildi.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        logger.error(f"Event loop xatosi: {e}")
        raise