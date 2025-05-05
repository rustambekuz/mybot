import requests
import logging
import json

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
API_URL = "https://auto-download-all-in-one.p.rapidapi.com/v1/social/autolink"
RAPIDAPI_KEY = "cc1b311428msh8e7eac8a9647690p1aea34jsnb448080c73a6"
RAPIDAPI_HOST = "auto-download-all-in-one.p.rapidapi.com"

def download_tiktok_video(url: str) -> str:
    """TikTok videoni RapidAPI orqali yuklab olish"""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }
    payload = {
        "url": url
    }

    try:
        logger.info(f"API so'rovi yuborildi: {API_URL} bilan {json.dumps(payload)}")
        response = requests.post(API_URL, headers=headers, json=payload)
        logger.info(f"API javobi: {response.status_code} - {response.text[:500]}")

        if response.status_code != 200:
            logger.error(f"API xatosi: HTTP {response.status_code}")
            return f"❌ API xatosi: HTTP {response.status_code}. Keyinroq urinib ko'ring."

        data = response.json()
        if not data or 'download_url' not in data:
            logger.error(f"API javobi noto'g'ri formatda: {data}")
            return "❌ Yuklab olish URL'i topilmadi. API javobi noto'g'ri."

        download_url = data.get('download_url')
        return download_url if download_url else "❌ Yuklab olish URL'i mavjud emas."

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
    """Asosiy funksiya: TikTok video URL'sini kiriting va yuklab olish linkini oling"""
    tiktok_url = "https://www.tiktok.com/@yeuphimzz/video/7237370304337628442"
    download_link = download_tiktok_video(tiktok_url)
    print(f"📥 TikTok video yuklab olish linki:\n{download_link}")

if __name__ == "__main__":
    main()