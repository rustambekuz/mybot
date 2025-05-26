from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from telegraph import Telegraph



class SubjectCallbackFactory(CallbackData, prefix="subject"):
    subject: str


class CategoryCallbackFactory(CallbackData, prefix="category"):
    subject: str
    category: str


class StartTestCallbackFactory(CallbackData, prefix="starttest"):
    subject: str
    category: str


class AnswerCallbackFactory(CallbackData, prefix="answer"):
    index: int
    selected_option: str



from aiogram.fsm.state import State, StatesGroup

class QuizStates(StatesGroup):
    question = State()



subjects = {
    "matematika": ["Algebra", "Geometriya", "Matematika test"],
    "fizika": ["Mexanika", "Optika", "Termodinamika"],
    "english": ["Grammar", "Vocabulary", "Listening"],
    "tarix": ["Jahon tarixi", "O‘zbekiston tarixi", "Qadimgi dunyo"]
}

def menu():
    keyboard = [
                  [KeyboardButton(text='📝 Testlar'),KeyboardButton(text='📈 Statistika')],
                  [KeyboardButton(text='📲 Admin bilan bog‘lanish')]
            ]
    murkup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return murkup


def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    for subject in subjects.keys():
        builder.button(
            text=subject.capitalize(),
            callback_data=SubjectCallbackFactory(subject=subject).pack()
        )
    builder.adjust(2)
    return builder.as_markup()


def get_subcategories_kb(subject: str):
    builder = InlineKeyboardBuilder()
    for category in subjects.get(subject, []):
        builder.button(
            text=category,
            callback_data=CategoryCallbackFactory(subject=subject, category=category).pack()
        )
    builder.button(text="⬅️ Orqaga", callback_data="subject")
    builder.adjust(2)
    return builder.as_markup()



def get_start_test_keyboard(subject: str, category: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✏️Testni boshlash",
        callback_data=StartTestCallbackFactory(subject=subject, category=category).pack()
    )
    builder.button(text="⬅️ Orqaga", callback_data=SubjectCallbackFactory(subject=subject).pack())
    builder.adjust(1)
    return builder.as_markup()



from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import string

async def send_question(message, state, edit=False):
    data = await state.get_data()
    questions = data['questions']
    current_index = data.get('current_question', 0)

    import json
    question_text, options_json, question_id, correct_answer = questions[current_index]
    options = json.loads(options_json) if isinstance(options_json, str) else options_json

    question_number = current_index + 1
    full_text = f"Savol {question_number}/{len(questions)}\n\n{question_text}"

    buttons = [
        InlineKeyboardButton(
            text=f"{letter}) {option}",
            callback_data=AnswerCallbackFactory(
                index=current_index,
                selected_option=option
            ).pack()
        )
        for letter, option in zip(string.ascii_uppercase, options)
    ]

    buttons_rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons_rows)

    if edit:
        await message.edit_text(full_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(full_text, reply_markup=keyboard, parse_mode="HTML")









