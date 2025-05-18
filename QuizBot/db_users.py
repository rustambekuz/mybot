import asyncpg

async def get_pool():
    return await asyncpg.create_pool(
        user='postgres',
        password='1234',
        database='userbot',
        host='localhost',
        port=5432
    )

async def save_user_if_not_exists(user_id: int, full_name: str, username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
                           INSERT INTO users (user_id, full_name, username)
                           VALUES ($1, $2, $3)
                               ON CONFLICT (user_id) DO NOTHING
                           """, user_id, full_name, username)

async def get_all_user_ids():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [r['user_id'] for r in rows]


