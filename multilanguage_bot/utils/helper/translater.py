
import json
from multilanguage_bot.main import BASE_DIR
from multilanguage_bot.utils.db.postgres_db import pgdb

def google_translate(chat_id):
    lang = pgdb.get_lang(chat_id) or 'uz'
    with open(f'{BASE_DIR}/locals/{lang}/data.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data



