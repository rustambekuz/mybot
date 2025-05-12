import logging
import json
from aiogram import Bot, Dispatcher, types
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = 'SIZNING_TOKENIZ'  # Tokeningizni shu yerga kiriting

YOUTUBE_API_KEY = 'YOUTUBE_API_KEY_HERE'  # Bu yerga YouTube API kalitini yozing

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

@dp.message_command('start')
async def send_welcome(message: types.Message):
    logger.info(f"Foydalanuvchi {message.from_user.id} /start buyrug'ini yubordi")
    await message.reply("Salom! Men musiqa botiman. Musiqa nomini yuboring, men sizga YouTube'dan havola topib beraman!")

@dp.message()
async def search_music(message: types.Message):
    query = message.text
    logger.info(f"Foydalanuvchi {message.from_user.id} qidiruv so'rovi: {query}")
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
            await message.reply(f"Topdim: {video_title}\nHavola: {video_url}")
            logger.info(f"Muvaffaqiyatli javob: {video_title} - {video_url}")
        else:
            await message.reply("Afsus, hech narsa topilmadi. Boshqa nomi bilan sinab ko'ring!")
            logger.warning(f"Qidiruv natijasiz: {query}")
    except HttpError as e:
        logger.error(f"YouTube API xatoligi: {e}")
        await message.reply("YouTube API bilan muammo yuz berdi. Iltimos, qaytadan urinib ko'ring.")
    except Exception as e:
        logger.error(f"Umumiy xatolik: {e}")
        await message.reply("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

async def main():
    await dp.start_polling()

if __name__ == '__main__':
    logger.info("Bot ishga tushmoqda...")
    asyncio.run(main())