import json

import requests
import logging

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API sozlamalari (RapidAPI orqali)
API_URL = "https://linkedin-data-api.p.rapidapi.com/profiles/positions/top"
RAPIDAPI_KEY = "cc1b311428msh8e7eac8a9647690p1aea34jsnb448080c73a6"
RAPIDAPI_HOST = "linkedin-data-api.p.rapidapi.com"

def get_top_position(username: str) -> str:
    """LinkedIn profilingizdagi eng yuqori lavozimni olish"""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    params = {
        "username": username
    }

    try:
        logger.info(f"API so'rovi yuborildi: {API_URL}?username={username}")
        response = requests.get(API_URL, headers=headers, params=params)
        logger.info(f"API javobi: {response.status_code} - {response.text[:500]}")

        if response.status_code != 200:
            logger.error(f"API xatosi: HTTP {response.status_code}")
            return f"❌ API xatosi: HTTP {response.status_code}. Keyinroq urinib ko'ring."

        data = response.json()
        if not data or 'position' not in data:
            logger.error(f"API javobi noto'g'ri formatda: {data}")
            return "❌ Lavozim ma'lumotlari topilmadi."

        position = data.get('position', 'Malumot yoq')
        company = data.get('company', 'Malumot yoq')
        return f"Eng yuqori lavozim: {position} - {company}"

    except requests.exceptions.RequestException as e:
        logger.error(f"So'rovda xato: {e}")
        return f"❌ So'rovda muammo yuz berdi: {str(e)}. Internetni tekshiring."
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing xatosi: {e}")
        return "❌ API javobi noto'g'ri formatda. Keyinroq urinib ko'ring."
    except Exception as e:
        logger.error(f"Kutilmagan xato: {e}")
        return f"❌ Noma'lum xato: {str(e)}. Keyinroq urinib ko'ring."

def main():
    """Asosiy funksiya: LinkedIn username'ini kiriting va eng yuqori lavozimni oling"""
    username = "adamselipsky"
    result = get_top_position(username)
    print(result)

if __name__ == "__main__":
    main()