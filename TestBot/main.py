import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher, html, F
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.filters.callback_data import CallbackData, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import asyncpg
from telegraph import Telegraph
from TestBot.db.db_quiz import get_connection_async

from inline_keyboards.keyboards import (
    get_main_keyboard, get_subcategories_kb, get_start_test_keyboard, menu,
    send_question, QuizStates,
    SubjectCallbackFactory, CategoryCallbackFactory, StartTestCallbackFactory, AnswerCallbackFactory
)

load_dotenv()

TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()




@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    conn = await get_connection_async()
    try:
        await conn.execute(
            """
            INSERT INTO users (user_id, full_name)
            VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE
                                             SET full_name = EXCLUDED.full_name
            """,
            message.from_user.id,
            message.from_user.full_name
        )
    finally:
        await conn.close()

    await message.answer(
        f"Assalomu alaykum, {html.bold(message.from_user.full_name)}!\n\n"
        f"Quyidagi tugmalardan birini tanlang:",
        reply_markup=menu()
    )



@dp.message(F.text == '📝 Testlar')
async def handle_test(message: Message):
    await message.answer("Bo'limlardan birini tanlang:", reply_markup=get_main_keyboard())
    await message.delete()


@dp.message(F.text == '📲 Admin bilan bog‘lanish')
async def handle_admin_contact(message: Message):
    await message.answer(
        f"Assalomu alaykum, {html.bold(message.from_user.full_name)}!\n\n"
        f"Admin bilan bog‘lanish uchun quyidagilarga murojaat qilishingiz mumkin\n"
        f"<b>Telegram username:</b> @freelancerpragrammiz\n"
        f"<b>📲Telefon raqam:</b>\n"
        f"{html.italic('+998 88-203-44-03')}\n"
        f"{html.italic('+998 95-071-71-03')}\n"
    )
    await message.delete()


@dp.message(F.text == "📈 Statistika")
async def show_statistics(message: Message):
    conn = await get_connection_async()
    try:
        users = await conn.fetch("SELECT id, user_id, full_name FROM users ORDER BY full_name")

        if not users:
            await message.answer("Hozircha hech qanday foydalanuvchi statistika mavjud emas.")
            await conn.close()
            return

        telegraph = Telegraph()
        telegraph.create_account(short_name='QuizBotUser')

        content_lines = ["<b>📊 Umumiy statistika natijalari<br>"
                         "Quyidagi jadvalda foydalanuvchilarning testdagi ishtiroki ko'satilgan:</b><br><br>"]

        for i, user in enumerate(users, start=1):
            last_5_answers = await conn.fetch(
                """
                SELECT is_correct
                FROM user_answer
                WHERE user_id = $1
                ORDER BY answered_at DESC NULLS LAST, id DESC
                    LIMIT 5
                """,
                user['user_id']
            )

            total = len(last_5_answers)
            correct = sum(1 for ans in last_5_answers if ans['is_correct'])
            incorrect = total - correct
            accuracy = (correct / total * 100) if total > 0 else 0.0

            if total == 0:
                continue

            user_stats = (
                f"<b>👤 {i}.{user['full_name'] or 'Ismi mavjud emas'}</b><br>"
                f"📝 Jami savollar: {total} ta<br>"
                f"✅ To'g'ri javoblar: {correct} ta<br>"
                f"❌ Noto'g'ri javoblar: {incorrect} ta<br>"
                f"📈 Natija foizi: {accuracy:.2f}%<br><br>"
            )
            content_lines.append(user_stats)

        content = "".join(content_lines)

        response = telegraph.create_page(
            title='Statistika',
            html_content=content
        )
        telegraph_url = response['url']

    finally:
        await conn.close()

    await message.answer(f'<a href="{telegraph_url}">Statistika natijalari 👇</a> ', parse_mode='HTML')


@dp.callback_query(SubjectCallbackFactory.filter())
async def subject_selected_handler(call: CallbackQuery, callback_data: SubjectCallbackFactory):
    subject = callback_data.subject
    await call.message.edit_text(
        text=f"📘 {subject.capitalize()} fanidan qaysi bo'limni ishlamoqchisiz!",
        reply_markup=get_subcategories_kb(subject)
    )


@dp.callback_query(lambda c: c.data == 'subject')
async def back_subject_handler(call: CallbackQuery):
    await call.message.edit_text(
        text="Fanlardan birini tanlang!", reply_markup=get_main_keyboard()
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

    conn = await get_connection_async()
    try:
        await conn.execute(
            """
            INSERT INTO user_answer (user_id, question_id, selected_answer, is_correct, answered_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            call.from_user.id, question_id, selected, is_correct
        )
    finally:
        await conn.close()

    await state.update_data(current_question=index + 1)

    if index + 1 < len(questions):
        await send_question(call.message, state, edit=True)
    else:
        await call.message.edit_text("✅ Test yakunlandi.")
        await state.clear()

    await call.answer()


@dp.callback_query(StartTestCallbackFactory.filter())
async def start_test_handler(call: CallbackQuery, callback_data: StartTestCallbackFactory, state: FSMContext):
    conn = await get_connection_async()
    try:
        category_row = await conn.fetchrow(
            """
            SELECT id FROM categories WHERE subject = $1 AND name = $2
            """,
            callback_data.subject, callback_data.category
        )

        if not category_row:
            await call.message.answer("❌ Kategoriya topilmadi.")
            return

        category_id = category_row['id']

        questions = await conn.fetch(
            """
            SELECT question_text, options, id, correct_answer FROM questions
            WHERE category_id = $1 LIMIT 5
            """,
            category_id
        )

        if not questions:
            await call.message.answer("❌ Bu kategoriyada savollar mavjud emas")
            return

        await state.update_data(
            subject=callback_data.subject,
            category=callback_data.category,
            questions=[(q['question_text'], q['options'], q['id'], q['correct_answer']) for q in questions],
            current_question=0,
            correct_count=0
        )

        await call.message.delete_reply_markup()
        await send_question(call.message, state)
        await state.set_state(QuizStates.question)
    finally:
        await conn.close()


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
    await message.answer(
        "❗️ Iltimos test ishlash uchun /start tugmasini bosing.",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.delete()


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
