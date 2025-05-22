from aiogram import html, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from multilanguage_bot.utils.db.postgres_db import pgdb
from multilanguage_bot.keyboards.inline import three_languages
from multilanguage_bot.utils.helper.translater import google_translate

start_router = Router()


@start_router.message(CommandStart())
async def command_start_handler(message: Message):
    chat_id = message.chat.id
    lang = message.from_user.language_code or 'uz'
    pgdb.db_save(chat_id, lang)

    texts = google_translate(chat_id)

    await message.answer(
        f"{texts['greeting']} {html.bold(message.from_user.full_name)}! 👋\n\n"
        f"🌐 {texts['choose_language']}\n"
        f"✳️ /language - {texts['change_language']}\n"
        f"💱 /kurs - {texts['currency_info']}",
        reply_markup=three_languages()
    )


@start_router.message(Command('language'))
async def command_language_handler(message: Message):
    texts = google_translate(message.chat.id)
    await message.answer(
        f"🌐 {texts['choose_language']}",
        reply_markup=three_languages()
    )

@start_router.callback_query(F.data.in_({"uz", "ru", "en"}))
async def language_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    lang = callback.data
    pgdb.db_save(chat_id, lang)

    texts = google_translate(chat_id)

    await callback.answer(texts["saved"], show_alert=True)

    await callback.message.edit_text(texts["selected_language"].format(lang=lang.upper()))

    await callback.message.answer(
        f"{texts['greeting']} {html.bold(callback.from_user.full_name)}! 👋\n\n"
        f"🌐 {texts['choose_language']}\n"
        f"✳️ /language - {texts['change_language']}\n"
        f"💱 /kurs - {texts['currency_info']}",
        reply_markup=three_languages()
    )
