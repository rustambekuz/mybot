import os
import re
import logging
import html
import aiofiles
import asyncio
import signal
import psutil
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from uuid import uuid4
import ffmpeg

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

# Deezer API sozlamalari (RapidAPI orqali)
DEEZER_API_URL = "https://deezer-public-api.p.rapidapi.com/search"
RAPIDAPI_KEY = "cc1b311428msh8e7eac8a9647690p1aea34jsnb448080c73a6"  # RapidAPI'dan olingan API Key'ni bu yerga qo'ying
RAPIDAPI_HOST = "deezer-downloader1.p.rapidapi.com"

# Telegram bot tokeni
TOKEN = "7328515791:AAGfDjpJ8uV-IGuIwrYZSi6HVrbu41MRwk4"

def clean_title(title: str) -> tuple[str, str]:
    """Deezer trek sarlavhasini tozalash va artist bilan qo'shiq nomini ajratish"""
    title = html.unescape(title).replace("'", "'")
    title = re.sub(r'\s*\[.*?\]', '', title)
    title = re.sub(r'\s*Official Audio.*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+', ' ', title).strip()

    if " - " in title:
        artist, song = title.split(" - ", 1)
    else:
        artist, song = "", title

    artist = re.sub(r'\s+', ' ', artist).strip()
    song = re.sub(r'\s+', ' ', song).strip()

    if not song and artist:
        song = artist
        artist = ""

    return artist, song

def format_filename(title: str) -> str:
    """Fayl nomi uchun maxsus belgilar va bo'shliqlarni tozalash"""
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'\s+', '_', title).strip()
    return title[:50]

async def download_audio(download_url: str, filename: str) -> bool:
    """Deezer preview URL'dan audio yuklash"""
    logger.info(f"Deezer preview URL'dan audio yuklash boshlandi: {download_url}")
    try:
        response = requests.get(download_url, stream=True)
        if response.status_code != 200:
            logger.error(f"Yuklab olish URL'dan xato: HTTP {response.status_code}")
            return False

        temp_file = f"{filename}.mp3"
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Vaqtinchalik fayl saqlandi: {temp_file}")

        output_file = f"{filename}_converted.mp3"
        stream = ffmpeg.input(temp_file)
        stream = ffmpeg.output(stream, output_file, format='mp3', acodec='mp3', ab='192k')
        ffmpeg.run(stream)
        logger.info(f"Fayl MP3 ga o'zgartirildi: {output_file}")

        if os.path.exists(temp_file):
            os.remove(temp_file)
            logger.info(f"Vaqtinchalik fayl o'chirildi: {temp_file}")
        os.rename(output_file, temp_file)
        return True
    except Exception as e:
        logger.error(f"Audio yuklashda xato: {e}")
        return False
    finally:
        for ext in ['mp3']:
            path = f"{filename}.{ext}"
            if os.path.exists(path):
                logger.info(f"Vaqtinchalik fayl o'chirilmoqda: {path}")
                os.remove(path)
            path = f"{filename}_converted.{ext}"
            if os.path.exists(path):
                logger.info(f"Vaqtinchalik fayl o'chirilmoqda: {path}")
                os.remove(path)

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi yuborgan so'rov bo'yicha Deezer'da musiqa qidirish"""
    query_text = update.message.text
    await update.message.reply_text("🔎 Qidirilmoqda, biroz kuting...")

    try:
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        params = {
            "q": query_text,
            "limit": 1
        }
        response = requests.get(DEEZER_API_URL, headers=headers, params=params)
        logger.info(f"API javobi: {response.text[:500]}")  # Javobning boshini log qilish
        if response.status_code != 200:
            logger.error(f"Deezer API xatosi: HTTP {response.status_code}")
            await update.message.reply_text(f"❌ Deezer API xatosi: HTTP {response.status_code}. Keyinroq urinib ko'ring.")
            return

        data = response.json()
        if not data or 'data' not in data:
            logger.error(f"API javobi noto'g'ri formatda: {data}")
            await update.message.reply_text("❌ Deezer API'dan noto'g'ri javob keldi. Keyinroq urinib ko'ring.")
            return

        results = data.get('data', [])
        if not results:
            await update.message.reply_text("❌ Hech narsa topilmadi. Boshqa so'rov yuborib ko'ring.")
            return

        track = results[0]
        raw_title = track['title']
        artist = track['artist']['name']
        full_title = f"{artist} - {raw_title}" if artist else raw_title
        preview_url = track.get('preview')

        logger.info(f"Tozalangan sarlavha: {full_title}")

        if not preview_url:
            await update.message.reply_text(
                f"🎵 Topildi: {full_title}\n"
                "❌ Afsuski, bu trekning preview versiyasi mavjud emas. Boshqa qo'shiqni sinab ko'ring."
            )
            return

        await update.message.reply_text(f"⬇️ Yuklanmoqda: {full_title}")

        filename = f"audio_{uuid4().hex}"
        formatted_filename = format_filename(full_title)

        if await download_audio(preview_url, filename):
            try:
                async with aiofiles.open(f"{filename}.mp3", 'rb') as audio:
                    await update.message.reply_audio(
                        audio=await audio.read(),
                        title=raw_title,
                        performer=artist if artist else None,
                        caption=f"🎵 {full_title} (Deezer)",
                        filename=f"{formatted_filename}.mp3"
                    )
                    logger.info(f"Audio muvaffaqiyatli yuborildi: {full_title}")
            except Exception as e:
                logger.error(f"Audio yuborishda xato: {e}")
                await update.message.reply_text("❌ Audio yuborishda xato yuz berdi.")
            finally:
                if os.path.exists(f"{filename}.mp3"):
                    logger.info(f"Audio fayl o'chirilmoqda: {filename}.mp3")
                    os.remove(f"{filename}.mp3")
        else:
            await update.message.reply_text(
                "❌ Audio yuklashda xato yuz berdi. Iltimos, boshqa qo'shiqni sinab ko'ring."
            )
    except Exception as e:
        logger.error(f"Deezer qidiruvida xato: {e}")
        await update.message.reply_text(f"❌ Deezer bilan muammo yuz berdi: {str(e)}. Keyinroq urinib ko'ring.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushirish uchun /start buyrug'i"""
    user = update.effective_user
    await update.message.reply_text(
        f"Salom, {user.first_name}!\n"
        "Qo'shiq nomini yuboring, masalan: Janob Rasul - Super\n"
        "Bot Deezer'dan qo'shiq qidiradi va preview yuklaydi."
    )

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
        webhook_info = await application.bot.get_webhook_info()
        logger.info(f"Webhook holati: {webhook_info}")
    except Exception as e:
        logger.error(f"Webhook o'chirishda xato: {e}")

def terminate_other_instances() -> None:
    """Boshqa bot jarayonlarini to'xtatish"""
    current_pid = os.getpid()
    bot_token = TOKEN.split(':')[0]
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.cmdline())
            if (proc.pid != current_pid and
                    'python' in proc.name().lower() and
                    bot_token in cmdline):
                logger.info(f"Eski bot jarayoni aniqlandi (PID: {proc.pid}, cmdline: {cmdline}), to'xtatilmoqda...")
                try:
                    proc.send_signal(signal.SIGTERM)
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    logger.warning(f"Jarayon (PID: {proc.pid}) SIGTERM bilan to'xtamadi, SIGKILL yuborilmoqda...")
                    proc.send_signal(signal.SIGKILL)
                    proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            logger.warning(f"Jarayon to'xtatishda xato (PID: {proc.pid}): {e}")
            continue

async def main() -> None:
    """Botni ishga tushirish"""
    global application
    try:
        logger.info("Eski bot jarayonlarini tozalash...")
        terminate_other_instances()

        application = Application.builder().token(TOKEN).build()

        await clear_webhook(application)

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
        application.add_error_handler(error_handler)

        logger.info("Bot ishga tushdi...")

        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=10
        )

        while True:
            await asyncio.sleep(3600)

    except Exception as e:
        logger.error(f"Botni ishga tushirishda xato: {e}")
        raise
    finally:
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