from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext



class SubjectCallbackFactory(CallbackData, prefix="subject"):
    subject: str


class CategoryCallbackFactory(CallbackData, prefix="category"):
    subject: str
    category: str


class StartTestCallbackFactory(CallbackData, prefix="starttest"):
    subject: str
    category: str



from aiogram.fsm.state import State, StatesGroup

class QuizStates(StatesGroup):
    question = State()



subjects = {
    "matematika": ["Algebra", "Geometriya", "Matematika test"],
    "fizika": ["Mexanika", "Optika", "Termodinamika"],
    "english": ["Grammar", "Vocabulary", "Listening"],
    "kimyo": ["Organik", "Anorganik", "Analitik"],
    "biologiya": ["Botanika", "Zoologiya", "Genetika"],
    "geografiya": ["Materiklar", "Iqlim", "Xaritalar"],
    "tarix": ["Jahon tarixi", "O‘zbekiston tarixi", "Qadimgi dunyo"],
    "adabiyot": ["She’riyat", "Nasr", "Adabiy tahlil"],
    "ona_tili": ["Fonetika", "Sintaksis", "Leksikologiya"],
}

def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    for subject in subjects.keys():
        builder.button(
            text=subject.capitalize(),
            callback_data=SubjectCallbackFactory(subject=subject).pack()
        )
    builder.adjust(3)
    return builder.as_markup()


def get_subcategories_kb(subject: str):
    builder = InlineKeyboardBuilder()
    for category in subjects.get(subject, []):
        builder.button(
            text=category,
            callback_data=CategoryCallbackFactory(subject=subject, category=category).pack()
        )
    builder.button(text="⬅️ Orqaga", callback_data="back_subjects")
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


async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data['current_question']
    questions = data['questions']

    question_text, options = questions[index]

    keyboard = [KeyboardButton(text=option) for option in options]
    keyboard = [keyboard[i:i + 2] for i in range(0, len(keyboard), 2)]


    markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

    await message.answer(f"{index + 1}-savol:\n\n{question_text}", reply_markup=markup)








