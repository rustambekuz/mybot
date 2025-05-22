
from aiogram import Router, F
from aiogram.types import Message
from multilanguage_bot.utils.helper.translater import google_translate
from multilanguage_bot.utils.currency_api import get_currency_rates

currency_router = Router()

@currency_router.message(F.text.startswith('/kurs'))
async def currency_handler(message: Message):
    chat_id = message.chat.id
    texts = google_translate(chat_id)

    args = message.text.split()
    if len(args) != 2:
        await message.answer(texts["currency_example"])
        return

    currency_code = args[1].upper()

    rates = await get_currency_rates()
    if not rates:
        await message.answer("API bilan bog'lanishda muammo yuz berdi.")
        return

    rate = rates.get(currency_code)
    if rate is None:
        await message.answer(texts["currency_not_found"])
        return

    await message.answer(
        f"{texts['currency_info']}\n\n"
        f"1 USD = {rate} {currency_code}"
    )
