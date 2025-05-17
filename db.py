import asyncpg

DB_CONFIG={
    "user": "postgres",
    "password": "1234",
    "database": "userbot",
    "host": "localhost",
    "port": 5432
}

async def insert_user(chat_id:int, fullname:str, phone:str, address:str):
    conn = await asyncpg.connect(**DB_CONFIG)
    await conn.execute("""INSERT INTO users (chat_id, fullname, phone, address) 
                          VALUES ($1, $2, $3, $4)""", chat_id, fullname, phone, address)
    await conn.close()

async def user_exists(chat_id):
    conn = await asyncpg.connect(**DB_CONFIG)
    user = await conn.fetchval("""SELECT 1 FROM users WHERE chat_id = $1""", chat_id)
    await conn.close()
    return user is not None






