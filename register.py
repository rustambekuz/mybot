import asyncio
import logging
import sys
from os import getenv
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv

from db import user_exists, insert_user
import asyncpg
from db import DB_CONFIG

load_dotenv()

TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher(storage=MemoryStorage())

class Register(StatesGroup):
    fullname=State()
    phone=State()
    address=State()

keyboard = [
    [KeyboardButton(text="shere contact", request_contact=True)]
]

kb_markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)




@dp.message(CommandStart())
async def command_start_handler(message: Message, state:FSMContext) -> None:
    chat_id = str(message.chat.id)

    if await user_exists(chat_id):
        await message.answer(f"Salom {message.from_user.full_name}, siz allaqachon ro'yxatdan o'tgansz!")
        return

    await state.set_state(Register.fullname)
    await message.answer("👨‍🦰 Ism-Familiyangizni kiriting!: ")

@dp.message(Register.fullname)
async def fullname_handler(message: Message, state:FSMContext) -> None:
    await state.update_data(fullname=message.text)
    await state.set_state(Register.phone)
    await message.answer("📲 Telefon raqamingizni kiriting", reply_markup=kb_markup)

@dp.message(Register.phone)
async def phone_handler(message: Message, state:FSMContext) -> None:
    await state.update_data(phone=message.text)
    await state.update_data(chat_id=str(message.chat.id))
    await state.set_state(Register.address)
    await message.answer("Manzil raqamingizni kiriting:")



@dp.message(Register.address)
async def address_handler(message: Message, state:FSMContext) -> None:
    await state.update_data(address=message.text)
    data = await state.get_data()
    chat_id = data['chat_id']

    if await user_exists(chat_id):
        await message.answer(f"Salom! {html.bold(message.from_user.full_name)}, siz allaqachon ro'yxatdan o'tgansz")
    else:
        await insert_user(
            chat_id=chat_id,
            fullname=data['fullname'],
            phone=data['phone'],
            address=data['address']
        )
        await message.answer("🎉 Siz muvofaqqiyatli ro'yxatdan o'tdingiz!", reply_markup=ReplyKeyboardRemove())

    await state.clear()


@dp.message(Command("followers"))
async def get_users_count(message: Message) -> None:
    conn = await asyncpg.connect(**DB_CONFIG)
    count = await conn.fetchval("SELECT COUNT(*) FROM users")
    await conn.close()
    await message.answer(f"Jami foydalanuvchilar soni: {count} ta!")


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