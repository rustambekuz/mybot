import asyncio
import logging
import sys
import os
from os import getenv
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pytube import YouTube
from moviepy.editor import AudioFileClip  # Konvertatsiya uchun

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# .env faylini yuklash
load_dotenv()
TELEGRAM_TOKEN = getenv("TELEGRAM_TOKEN")
YOUTUBE_API_KEY = getenv("YOUTUBE_API_KEY")

if not TELEGRAM_TOKEN or not YOUTUBE_API_KEY:
    logger.error("TELEGRAM_TOKEN yoki YOUTUBE_API_KEY topilmadi!")
    raise ValueError("TELEGRAM_TOKEN va YOUTUBE_API_KEY .env faylida sozlanmagan!")

# YouTube API bilan ulanish
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, cache_discovery=False)

# Dispatcher yaratish
dp = Dispatcher()

# Yuklash uchun papka
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# /start komandasi uchun handler
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    logger.info(f"Foydalanuvchi {message.from_user.id} /start yubordi")
    await message.answer(
        f"Salom, {html.bold(message.from_user.full_name)}!\n"
        "Musiqa nomini yuboring, men uni YouTube'dan topib, audio sifatida yuboraman!"
    )

# Matnli xabar uchun handler
@dp.message()
async def search_music_handler(message: Message) -> None:
    query = message.text.strip()
    if not query:
        await message.answer("Iltimos, musiqa nomini kiriting.")
        return

    logger.info(f"Qidiruv so'rovi: {query}")
    try:
        request = youtube.search().list(
            part="snippet",
            maxResults=1,
            q=query,
            type="video"
        )
        response = request.execute()

        if response['items']:
            video_id = response['items'][0]['id']['videoId']
            video_title = response['items'][0]['snippet']['title']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            logger.info(f"Topilgan video: {video_title} ({video_url})")

            yt = YouTube(video_url)
            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()

            if not audio_stream:
                await message.answer("Audio topilmadi, boshqa nom bilan urinib ko'ring.")
                return

            # Fayl yo'llari
            video_file_path = os.path.join(DOWNLOAD_PATH, f"{video_id}.mp4")
            mp3_file_path = os.path.join(DOWNLOAD_PATH, f"{video_id}.mp3")

            # Yuklab olish
            audio_stream.download(output_path=DOWNLOAD_PATH, filename=f"{video_id}.mp4")

            # MP3 formatga o‘tkazish
            try:
                clip = AudioFileClip(video_file_path)
                clip.write_audiofile(mp3_file_path)
                clip.close()
                os.remove(video_file_path)
            except Exception as e:
                logger.error(f"Konvertatsiya xatoligi: {e}")
                await message.answer("Audio faylni tayyorlashda xatolik yuz berdi.")
                return

            # Telegramga yuborish
            audio = FSInputFile(mp3_file_path, filename=f"{video_title}.mp3")
            await message.answer_audio(
                audio=audio,
                caption=f"{html.bold(video_title)}"
            )

            logger.info(f"Yuborildi: {video_title}")
            os.remove(mp3_file_path)
        else:
            await message.answer("Hech narsa topilmadi.")
    except HttpError as e:
        logger.error(f"YouTube API xatolik: {e}")
        await message.answer("YouTube API bilan bog‘liq muammo. Keyinroq urinib ko‘ring.")
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await message.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko‘ring.")

# Botni ishga tushirish
async def main() -> None:
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info("Bot ishga tushdi.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


