import logging
import boto3
import json
from aiogram import Bot, Dispatcher, executor, types
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Logging sozlamalari (CloudWatch uchun moslashtirilgan)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Secrets Manager'dan ma'lumotlarni olish
def get_secrets():
    session = boto3.session.Session()
    client = session.client('secretsmanager', region_name='us-east-1')  # O'zingizning regioningizni kiriting
    try:
        secret = client.get_secret_value(SecretId='music_bot_secrets')
        return json.loads(secret['SecretString'])
    except Exception as e:
        logger.error(f"Secrets Manager xatoligi: {e}")
        raise ValueError("Secrets Manager'dan ma'lumot olishda xato!")

secrets = get_secrets()
TELEGRAM_TOKEN = secrets['TELEGRAM_TOKEN']
YOUTUBE_API_KEY = secrets['YOUTUBE_API_KEY']

# Token va API kalitini tekshirish
if not TELEGRAM_TOKEN or not YOUTUBE_API_KEY:
    logger.error("TELEGRAM_TOKEN yoki YOUTUBE_API_KEY topilmadi!")
    raise ValueError("TELEGRAM_TOKEN va YOUTUBE_API_KEY sozlanmagan!")

# Botni ishga tushirish
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# YouTube API bilan ulanish
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# /start buyrug'i uchun handler
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    logger.info(f"Foydalanuvchi {message.from_user.id} /start buyrug'ini yubordi")
    await message.reply("Salom! Men musiqa botiman. Musiqa nomini yuboring, men sizga YouTube'dan havola topib beraman!")

# Matnli xabarlar uchun handler
@dp.message_handler()
async def search_music(message: types.Message):
    query = message.text
    logger.info(f"Foydalanuvchi {message.from_user.id} qidiruv so'rovi: {query}")
    try:
        # YouTube'da qidiruv
        request = youtube.search().list(
            part="snippet",
            maxResults=1,
            q=query,
            type="video"
        )
        response = request.execute()

        # Natijalarni olish
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

# Botni ishga tushirish
if __name__ == '__main__':
    logger.info("Bot ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True)