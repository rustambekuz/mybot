
import aiohttp
from os import getenv

API_KEY = getenv("EXCHANGE_API_KEY")
BASE_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD"

async def get_currency_rates():
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("conversion_rates", {})
            else:
                return {}
