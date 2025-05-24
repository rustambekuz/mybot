import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher, html
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.filters.callback_data import CallbackData, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message, ReplyKeyboardMarkup,ReplyKeyboardRemove, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from TestBot.db.db_quiz import get_connection
from inline_keyboards.keyboards import get_main_keyboard, get_subcategories_kb, get_start_test_keyboard
from inline_keyboards.keyboards import send_question, QuizStates
from dotenv import load_dotenv

load_dotenv()

TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()



@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!\n\n"
                         f"Test ishlash uchun fanlardan birini tanlang",
                         reply_markup=get_main_keyboard())


from inline_keyboards.keyboards import SubjectCallbackFactory, CategoryCallbackFactory, StartTestCallbackFactory
@dp.callback_query(SubjectCallbackFactory.filter())
async def subject_selected_handler(call: CallbackQuery, callback_data: SubjectCallbackFactory):
    subject = callback_data.subject
    await call.message.edit_text(
        text=f"📘 {subject.capitalize()} fanidan qaysi bo'limni ishlamoqchisiz!",
        reply_markup=get_subcategories_kb(subject)
    )



@dp.callback_query(lambda c: c.data == 'back_subjects')
async def back_subject_handler(call:CallbackQuery):
    await call.message.edit_text(
        text="Fanlardan birini tanlang!",reply_markup=get_main_keyboard()
    )
    await call.answer()


@dp.message(QuizStates.question)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    current_question = data.get('current_question', 0)
    questions = data.get('questions', [])

    current_question += 1

    if current_question >= len(questions):
        await message.answer("✅ Test tugadi!\n\n"
                             "Yana test ishlashni hohlasangiz /start tugmasini bosing!", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    await state.update_data(current_question=current_question)
    await send_question(message, state)


@dp.callback_query(StartTestCallbackFactory.filter())
async def start_test_handler(call: CallbackQuery, callback_data: StartTestCallbackFactory, state: FSMContext):
    subject = callback_data.subject
    category = callback_data.category

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
                SELECT id FROM categories WHERE subject = %s AND name = %s
                """, (subject, category))
    category_row = cur.fetchone()

    if not category_row:
        await call.message.answer("❌ Kategoriya topilmadi.")
        return
    category_id = category_row[0]

    cur.execute("""
                SELECT question_text, options FROM questions
                WHERE category_id = %s LIMIT 5
                """, (category_id,))
    questions = cur.fetchall()
    conn.close()

    if not questions:
        await call.message.answer("❌ Bu kategoriyada savollar mavjud emas")
        return

    await state.update_data(
        subject=subject,
        category=category,
        questions=questions,
        current_question=0
    )

    await call.message.delete_reply_markup()
    await send_question(call.message, state)
    await state.set_state(QuizStates.question)


@dp.callback_query(CategoryCallbackFactory.filter())
async def category_selected_handler(call: CallbackQuery, callback_data: CategoryCallbackFactory):
    subject = callback_data.subject
    category = callback_data.category
    await call.message.edit_text(
        text=f"Siz {subject} fandan {category} yo'nalishi bo‘yicha test ishlaysiz!",
        reply_markup=get_start_test_keyboard(subject, category)
    )
    await call.answer()


@dp.message()
async def default_message_handler(message: Message):
      await message.answer("❗️ Iltimos test ishlash uchun /start tugmasini bosing.",
                               reply_markup=ReplyKeyboardRemove())
      await message.delete()


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
