from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def three_languages():
    kbs = [
        [
            InlineKeyboardButton(text='🇺🇿 uz', callback_data='uz'),
            InlineKeyboardButton(text='🇷🇺 ru', callback_data='ru'),
            InlineKeyboardButton(text='🇺🇸 en', callback_data='en'),

        ]
    ]

    uz_ru_en_kbs = InlineKeyboardMarkup(inline_keyboard=kbs)
    return uz_ru_en_kbs