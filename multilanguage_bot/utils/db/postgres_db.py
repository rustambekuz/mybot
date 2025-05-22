import psycopg2
from os import getenv
from dotenv import load_dotenv

load_dotenv()

class PsqlDB:
    def __init__(self):
        self.connect = psycopg2.connect(
            dbname=getenv('DB_NAME'),
            user=getenv('DB_USER'),
            password=getenv('PASSWORD'),
            host=getenv('HOST'),
            port=getenv('PORT')
        )
        self.cursor = self.connect.cursor()

    def execute(self, query, params=None):
        with self.connect:
            self.cursor.execute(query, params)
        return self.cursor

    def fetchone(self, query, params=None):
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def db_save(self, chat_id, lang):
        query = """INSERT INTO users (chat_id, lang) VALUES (%s, %s)
            ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang;"""
        self.execute(query, (chat_id, lang))

    def get_lang(self, chat_id):
        query = """SELECT lang FROM users WHERE chat_id = %s;"""
        result = self.fetchone(query, (chat_id,))
        return result[0] if result else None

pgdb = PsqlDB()
