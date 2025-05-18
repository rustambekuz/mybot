import asyncio
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from os import getenv

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from dbquiz import get_questions_from_db, Question

load_dotenv()
TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher(storage=MemoryStorage())

class Quiz(StatesGroup):
    confirmation = State()
    choosing_category = State()
    asking_question = State()

all_questions = get_questions_from_db()


def make_keyboards(options, row=2):
    keyboards = [KeyboardButton(text=str(o)) for o in options]
    keyboards = [keyboards[i:i + row] for i in range(0, len(keyboards), row)]

    markup = ReplyKeyboardMarkup(keyboard=keyboards, resize_keyboard=True)
    return markup


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"Salom, {html.bold(message.from_user.full_name)}!\n"
        f"Test ishlash uchun /play ni bosing!",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Command("play"))
async def play_handler(message: Message, state:FSMContext) -> None:
    await state.set_state(Quiz.confirmation)
    await message.answer("Test ishlaysizmi?", reply_markup=make_keyboards(["Yes", "No"]))

@dp.message(Quiz.confirmation)
async def confirmation_handler(message: Message, state:FSMContext) -> None:
    if message.text=='Yes':
        await state.set_state(Quiz.choosing_category)
        await message.answer("Kategoriyani tanlang:", reply_markup=make_keyboards(['Math', 'Physics', 'English']))
    else:
        await state.clear()
        await message.answer("Testni boshlash uchun /play ni bosing!", reply_markup=ReplyKeyboardRemove())


@dp.message(Quiz.choosing_category)
async def category_handler(message: Message, state: FSMContext) -> None:
    category=message.text
    category_questions = [q for q in all_questions if q.category == category]
    if not category_questions:
        await message.answer("Kategoriyada savollar mavjud emas!")
        return

    await state.set_state(Quiz.asking_question)
    await state.update_data(step=0, score=0, total=len(category_questions), questions=category_questions)
    question=category_questions[0]
    await message.answer(f"1-savol\n{question.text}", reply_markup=make_keyboards(question.options))


@dp.message(Quiz.asking_question)
async def asking_question_handler(message: Message, state:FSMContext) -> None:
    data=await state.get_data()
    step=data.get('step')
    score=data.get('score')
    total=data.get('total')
    questions = data.get('questions')

    correct_question = questions[step]
    if message.text==correct_question.correct_answer:
        await message.reply("✅ To'g'ri!")
        score+=1
    else:
        await message.reply("❌ Noto'g'ri!")

    step+=1

    if step>=total:
        await message.answer(f"Test tugadi\n"
                             f"{html.bold(message.from_user.full_name)}!, sizning test natijangiz quyidagicha\n"
                             f"To'g'ri javoblar {score}/{total}!", reply_markup=ReplyKeyboardRemove())
        await state.clear()
    else:
        await state.update_data(step=step, score=score)
        next_question = questions[step]
        await message.answer(f"{step+1}-savol\n{next_question.text}",
                             reply_markup=make_keyboards(next_question.options))
        
@dp.message()
async def default_message_handler(message: Message):
    await message.answer("Salom, Rustambek!\nTest ishlash uchun /play ni bosing!")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
