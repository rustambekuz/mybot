# import psycopg2
#
# def get_connection():
#     return psycopg2.connect(
#         dbname="quiztestbot",
#         user="postgres",
#         password="1234",
#         host="localhost",
#         port="5432"
#     )
#
#
#
# import asyncpg
#
# async def get_connection_async():
#     return await asyncpg.connect(
#         user='postgres',
#         password='1234',
#         database='quiztestbot',
#         host='localhost',
#         port=5432
#     )

import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="quiztestbot_db",
        user="quiztestbot_db_user",
        password="j1KFFJreLjozsMis9GmqilgqbsxU0IaF",
        host="dpg-d10m773e5dus73afg9b0-a",
        port="5432"
    )



import asyncpg

async def get_connection_async():
    return await asyncpg.connect(
        user='quiztestbot_db_user',
        password='j1KFFJreLjozsMis9GmqilgqbsxU0IaF',
        database='quiztestbot_db',
        host='dpg-d10m773e5dus73afg9b0-a',
        port=5432
    )


