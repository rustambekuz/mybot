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
    asking_question = State()

all_questions = get_questions_from_db()


def make_keyboards(options, row=2):
    keyboards = [KeyboardButton(text=str(o)) for o in options]
    keyboards = [keyboards[i:i + row] for i in range(0, len(keyboards), row)]

    markup = ReplyKeyboardMarkup(keyboard=keyboards, resize_keyboard=True)
    return markup


@dp.message(CommandStart())
async def command_start_handler(message: Message, state:FSMContext) -> None:
    await message.answer(
        f"Salom, {html.bold(message.from_user.full_name)}!\n"
        f"Test ishlash uchun /play ni bosing!",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Command("play"))
async def play_handler(message: Message, state:FSMContext) -> None:
    await state.set_state(Quiz.confirmation)
    await message.answer(f"Test ishlaysizmi? Savollar soni {len(all_questions)}", reply_markup=make_keyboards(["Yes", "No"]))

@dp.message()
@dp.message(Quiz.confirmation)
async def confirmation_handler(message: Message, state:FSMContext) -> None:
    if message.text=='Yes':
        await state.set_state(Quiz.asking_question)
        await state.update_data(step=0,score=0,total=len(all_questions))
        question=all_questions[0]
        await message.answer(question.text, reply_markup=make_keyboards(question.options))
    else:
        await state.clear()
        await message.answer("Testni boshlash uchun /play ni bosing!", reply_markup=ReplyKeyboardRemove())



@dp.message(Quiz.asking_question)
async def asking_question_handler(message: Message, state:FSMContext) -> None:
    data=await state.get_data()
    step=data['step']
    score=data['score']
    total=data['total']
    correct_question=all_questions[step]
    if message.text==correct_question.correct_answer:
        await message.answer("✅ To'g'ri!")
        score+=1
    else:
        await message.answer("❌ Noto'g'ri!")

    step+=1

    if step>=total:
        await message.answer(f"Test tugadi\nTo'g'ri javoblar soni: {score}/{total}!", reply_markup=ReplyKeyboardRemove())
        await state.clear()
    else:
        await state.update_data(step=step,score=score)
        next_question=all_questions[step]
        await message.answer(next_question.text, reply_markup=make_keyboards(next_question.options))




async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
