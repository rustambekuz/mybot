import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="quiztestbot",
        user="postgres",
        password="1234",
        host="localhost",
        port="5432"
    )



import asyncpg

async def get_connection_async():
    return await asyncpg.connect(
        user='postgres',
        password='1234',
        database='quiztestbot',
        host='localhost',
        port=5432
    )