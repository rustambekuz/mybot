import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
import sys
from os import getenv

from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()


@dataclass
class Question:
    text: str
    options: list[str]
    correct_answer: str


@dataclass
class Database:
    questions: list[Question]


matematika = [
    Question(text='2 * 4 = ?', options=['8', '9', '10', '11'], correct_answer='8'),
    Question(text='2 - 4 = ?', options=['-2', '3', '0', '1'], correct_answer='-2'),
    Question(text='2x * 4 = 0', options=['0', '9', '10', '11'], correct_answer='0'),
]

db = Database(questions=matematika)


@dataclass
class GameState:
    step: dict = field(default_factory=defaultdict)  # {"128389123": 0, "129232031":3, "2314141241": None}


dp['quizzes'] = db.questions
dp['game_state'] = GameState()


def make_keyboards(options, row=2):
    width = len(options)
    width = width + 1 if width % 2 != 0 else width
    keyboards = [KeyboardButton(text=str(o)) for o in options]
    keyboards = [keyboards[i:i + row] for i in range(0, width, row)]

    markup = ReplyKeyboardMarkup(keyboard=keyboards, resize_keyboard=True)
    return markup


async def send_question(message: Message, game_state: GameState, quizzes: list[Question]):
    chat_id = message.chat.id
    step = game_state.step.get(chat_id)
    if step >= len(quizzes):
        game_state.step[chat_id] = None
        return await message.answer('Savollar tugadi!\n\nQayta o`ynash uchun /play ni bosing!', reply_markup=ReplyKeyboardRemove())

    quiz = quizzes[step]
    text = f"{step + 1}-savol\n{quiz.text}"
    options = quiz.options
    await message.answer(text=text, reply_markup=make_keyboards(options))
    return None


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Salom, {html.bold(message.from_user.full_name)}!\n\n"
                         f"o'ynash uchun /play tugamasini bosing!", reply_markup=ReplyKeyboardRemove())


@dp.message(Command('play'))
async def game_confirm(message: Message, quizzes: list[Question]):
    await message.reply(text=f"Test {len(quizzes)} ta savoldan iborat!\n\n"
                             f"Boshlaymizmi? ", reply_markup=make_keyboards(['Ha', 'Yoq']))


@dp.message()
async def hand_answer(message: Message, game_state: GameState, quizzes: list[Question]):
    mg_txt = message.text
    chat_id = message.chat.id
    step = game_state.step.get(chat_id)

    if mg_txt == 'Ha':
        game_state.step[chat_id] = 0
        return await send_question(message, game_state, quizzes)

    if step is None or mg_txt == 'Yoq':
        return await message.answer('O`yinni boshlash uchun /play kamandasini bosing!',
                                    reply_markup=ReplyKeyboardRemove())
    correct_answer = quizzes[step].correct_answer
    if correct_answer == mg_txt:
        await message.answer('To`g`ri')
    else:
        await message.answer('Noto`g`ri')

    game_state.step[chat_id] += 1
    await send_question(message, game_state, quizzes)
    return None

async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
