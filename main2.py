import requests
import json
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

# Spotify API sozlamalari (RapidAPI orqali)
SPOTIFY_API_URL = "https://spotify23.p.rapidapi.com/track_lyrics/"
RAPIDAPI_KEY = "cc1b311428msh8e7eac8a9647690p1aea34jsnb448080c73a6"
RAPIDAPI_HOST = "spotify23.p.rapidapi.com"

def get_lyrics(track_id: str) -> str:
    """Spotify API'dan qo'shiq matnini olish"""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    params = {
        "id": track_id
    }

    try:
        response = requests.get(SPOTIFY_API_URL, headers=headers, params=params)
        logger.info(f"API so'rovi yuborildi: {SPOTIFY_API_URL}?id={track_id}")
        logger.info(f"API javobi: {response.status_code} - {response.text[:500]}")

        if response.status_code != 200:
            logger.error(f"Spotify API xatosi: HTTP {response.status_code}")
            return f"❌ Spotify API xatosi: HTTP {response.status_code}. Keyinroq urinib ko'ring."

        data = response.json()
        if not data or 'lyrics' not in data:
            logger.error(f"API javobi noto'g'ri formatda: {data}")
            return "❌ Spotify API'dan noto'g'ri javob keldi. Keyinroq urinib ko'ring."

        lyrics_data = data.get('lyrics', {})
        lines = lyrics_data.get('lines', [])
        if not lines:
            return "❌ Bu qo'shiq uchun lyrics topilmadi."

        # Lyrics matnini formatlash
        lyrics_text = "\n".join(line.get('words', '') for line in lines if line.get('words'))
        return lyrics_text if lyrics_text else "❌ Lyrics bo'sh yoki mavjud emas."

    except Exception as e:
        logger.error(f"Spotify qidiruvida xato: {e}")
        return f"❌ Spotify bilan muammo yuz berdi: {str(e)}. Keyinroq urinib ko'ring."

def main():
    """Asosiy funksiya: Qo'shiq ID'sini kiriting va lyrics oling"""
    track_id = "4snRyiaLyvTMui0hzp8MF7"  # Foydalanuvchi kiritgan qo'shiq ID'si
    lyrics = get_lyrics(track_id)
    print(f"🎵 Qo'shiq matni (Track ID: {track_id}):\n")
    print(lyrics)

if __name__ == "__main__":
    main()