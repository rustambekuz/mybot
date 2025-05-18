import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv

load_dotenv()

TOKEN = getenv("BOT_TOKEN")


dp = Dispatcher()

keyboards = [
    [KeyboardButton(text="shere contact1", request_contact=True), KeyboardButton(text="shere contact2", request_contact=True)],
]

kb_markup=ReplyKeyboardMarkup(keyboard=keyboards, resize_keyboard=True)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Hello, <b>{message.from_user.full_name}</b>!", reply_markup=kb_markup)


@dp.message()
async def echo_handler(message: Message) -> None:

    try:
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        await message.answer("Nice try!")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
