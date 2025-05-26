import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher, html
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.filters.callback_data import CallbackData, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message, ReplyKeyboardMarkup,ReplyKeyboardRemove, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from TestBot.db.db_quiz import get_connection
from inline_keyboards.keyboards import get_main_keyboard, get_subcategories_kb, get_start_test_keyboard, menu
from inline_keyboards.keyboards import send_question, QuizStates
from dotenv import load_dotenv

load_dotenv()

TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()



@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Assalomu alaykum, {html.bold(message.from_user.full_name)}!\n\n"
                         f"Quyidagi tugmalardan birini tanlang:",
                         reply_markup=menu())


@dp.message(F.text=='📝 Testlar')
async def handle_test(message: Message):
    await message.answer("Bo'limlardan birini tanlang:", reply_markup=get_main_keyboard())
    await message.delete()

@dp.message(F.text=='📲 Admin bilan bog‘lanish')
async def handle_test(message: Message):
    await message.answer(f"Assalomu alaykum, {html.bold(message.from_user.full_name)}!\n\n"
                         f"Admin bilan bog‘lanish uchun quyidagilarga murojaat qilishingiz mumkin\n"
                         f"Telegram username: @freelancerpragrammiz\n"
                         f"📲Telefon raqam:\n"
                         f"{html.italic('+998 88-203-44-03')}\n"
                         f"{html.italic('+998 95-071-71-03')}\n")
    await message.delete()



@dp.message(F.text == "📈 Statistika")
async def show_statistics(message: Message):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
                SELECT is_correct
                FROM user_answer
                WHERE user_id = %s
                ORDER BY id DESC
                    LIMIT 5
                """, (message.from_user.id,))
    results = cur.fetchall()
    conn.close()

    if not results:
        await message.answer("Siz hali testlarni yechmagansiz.")
        return

    total_answers = len(results)
    correct_answers = sum(1 for row in results if row[0])
    accuracy = (correct_answers / total_answers) * 100

    text = (
        f"📊 Test natijangiz:\n\n"
        f"Jami berilgan savollar soni: {total_answers} ta\n"
        f"To'g'ri javoblar soni: {correct_answers} ta\n"
        f"Noto'g'ri javoblar soni: {total_answers-correct_answers} ta\n"
        f"Natija foizi: {accuracy:.2f}%"
    )

    await message.answer(text)





from inline_keyboards.keyboards import SubjectCallbackFactory, CategoryCallbackFactory, StartTestCallbackFactory, AnswerCallbackFactory
@dp.callback_query(SubjectCallbackFactory.filter())
async def subject_selected_handler(call: CallbackQuery, callback_data: SubjectCallbackFactory):
    subject = callback_data.subject
    await call.message.edit_text(
        text=f"📘 {subject.capitalize()} fanidan qaysi bo'limni ishlamoqchisiz!",
        reply_markup=get_subcategories_kb(subject)
    )



@dp.callback_query(lambda c: c.data == 'subject')
async def back_subject_handler(call:CallbackQuery):
    await call.message.edit_text(
        text="Fanlardan birini tanlang!",reply_markup=get_main_keyboard()
    )
    await call.answer()


@dp.callback_query(AnswerCallbackFactory.filter())
async def handle_answer(call: CallbackQuery, callback_data: AnswerCallbackFactory, state: FSMContext):
    index = callback_data.index
    selected = callback_data.selected_option

    data = await state.get_data()
    questions = data['questions']
    current_question = questions[index]
    question_text, options_json, question_id, correct_answer = current_question

    is_correct = (selected == correct_answer)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
                INSERT INTO user_answer (user_id, question_id, selected_answer, is_correct, answered_at)
                VALUES (%s, %s, %s, %s, NOW())
                """, (call.from_user.id, question_id, selected, is_correct))
    conn.commit()
    conn.close()

    await state.update_data(current_question=index + 1)

    if index + 1 < len(questions):
        await send_question(call.message, state, edit=True)
    else:
        await call.message.edit_text("✅ Test yakunlandi.")
        await state.clear()

    await call.answer()





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
                SELECT question_text, options, id, correct_answer FROM questions
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
        current_question=0,
        correct_count=0
    )

    await call.message.delete_reply_markup()
    await send_question(call.message, state)
    await state.set_state(QuizStates.question)



@dp.callback_query(CategoryCallbackFactory.filter())
async def category_selected_handler(call: CallbackQuery, callback_data: CategoryCallbackFactory):
    subject = callback_data.subject
    category = callback_data.category
    await call.message.edit_text(
        text=f"Siz {subject} fanidan {category} yo'nalishi bo‘yicha test ishlaysiz!",
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
