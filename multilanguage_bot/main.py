import asyncio
import logging
import sys
from os import getenv, path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()
TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()

BASE_DIR = path.dirname(path.abspath(__file__))

async def main() -> None:
    from multilanguage_bot.handlers.start import start_router
    from multilanguage_bot.handlers.callback_queries import call_router
    from multilanguage_bot.handlers.currency import currency_router
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp.include_routers(start_router, call_router, currency_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())