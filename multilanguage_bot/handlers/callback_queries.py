from aiogram.types import CallbackQuery
from aiogram import F, Router

call_router = Router()

messages = {
    'uz': "🇺🇿 O'zbek tilini tanladingiz!",
    'ru': "🇷🇺 Вы выбрали русский язык!",
    'en': "🇺🇸 You chose English language!"
}

@call_router.callback_query(F.data.in_(messages.keys()))
async def lang_callback_handler(call: CallbackQuery):
    msg = messages.get(call.data)
    if msg:
        await call.message.answer(text=msg)


from multilanguage_bot.utils.db.postgres_db import pgdb

@call_router.callback_query(F.data.in_(messages.keys()))
async def lang_callback_handler(call: CallbackQuery):
    chat_id = call.message.chat.id
    lang = call.data
    msg = messages.get(lang)

    if msg:
        pgdb.db_save(chat_id, lang)
        await call.answer("Til saqlandi ✅", show_alert=True)
        await call.message.edit_text(msg)

