import psycopg2
from dataclasses import dataclass
@dataclass
class Question:
    text: str
    options: list[str]
    correct_answer: str
    category: str

def get_questions_from_db():
    conn = psycopg2.connect(
        dbname='userbot',
        user='postgres',
        password='1234',
        host='localhost'
    )
    cur = conn.cursor()
    cur.execute("""SELECT text, options, correct_answer, category FROM questions""")
    questions=[]
    for row in cur.fetchall():
        questions.append(Question(
            text=row[0],
            options=row[1],
            correct_answer=row[2],
            category=row[3]
        ))
    cur.close()
    conn.close()
    return questions
