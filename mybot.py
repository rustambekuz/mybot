import asyncio
import logging
import sys
import re
from os import getenv
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()
TOKEN = getenv("BOT_TOKEN")


dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:

    # await message.answer(f"Salom, {html.bold(message.from_user.full_name)}! tug'ilgan yilingizni kiriting men yoshingizni aytaman!")
    await message.answer("Tug'ilgan yilingizni kiriting men yoshingizni aytaman!")

@dp.message(F.text=="tel_user")
async def get_me(message: Message):
    chat_id = message.chat.id
    full_name = message.from_user.full_name
    text = message.text
    username = message.from_user.username
    await message.answer(f"Qabul qilindi! \n\nChat ID: {chat_id}\n"
                         f"Ism: {full_name}\n"
                         f"Username: @{username}\n"
                         f"{text}")

# @dp.message(F.text.regexp(r'(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})'))
# async def check_date(message: Message):
#     await message.answer("Sizdan date formatda malumot keldi!")

def calculate_age(birthdate):
    from datetime import datetime
    today = datetime.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

REGEXP_DATE=r"(?P<day>0?[1-9]|[12][0-9]|3[01])(?P<sep>[\/\-\.])(?P<month>0?[1-9]|1[0-2])(?P=sep)(?P<year>\d{4})"

@dp.message(F.text.regexp(REGEXP_DATE))
async def get_age_from_date(message: Message):
    match = re.search(REGEXP_DATE, message.text)
    if match:
        day_str = match.group('day')
        month_str = match.group('month')
        year_str = match.group('year')

        if None not in (day_str, month_str, year_str):
            try:
                day, month, year = int(day_str), int(month_str), int(year_str)
                from datetime import datetime
                birthdate = datetime(year, month, day)
                age = calculate_age(birthdate)
                await message.answer(f"Sizning yoshingiz: {age} yosh")
            except ValueError:
                await message.answer("Sanani noto‘g‘ri kiritdingiz.")
        else:
            await message.answer("Iltimos, sanani DD-MM-YYYY formatda yuboring.")
    else:
        await message.answer("Iltimos, sanani DD-MM-YYYY formatda yuboring.")

@dp.message()
async def echo_handler(message: Message) -> None:

    try:
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        await message.answer("Qaytadan urinib ko'ring!")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

