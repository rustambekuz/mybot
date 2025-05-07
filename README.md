MusiqaBot Telegram bot for downloading audio from YouTube and videos from Instagram. Features Download audio (MP3, 128 kbps) 
from YouTube videos or search by song name. Download videos (MP4) from public Instagram reels. Supports retry logic for handling 
timeouts and connection errors. Cleans video titles for better formatting in Telegram. Installation Clone the repository:git 
clone https://github.com/your-username/MusiqaBot.git cd MusiqaBot Create a virtual environment and install dependencies:python3 
-m venv .venv source .venv/bin/activate pip install -r requirements.txt Install FFmpeg (required for YouTube audio 
extraction):sudo apt update sudo apt install ffmpeg -y Create a .env file with the following 
keys:TELEGRAM_TOKEN=your-telegram-bot-token YOUTUBE_API_KEY=your-youtube-api-key (Optional) Add a cookies.txt file for 
YouTube/Instagram authentication: Place it in the project root (/path/to/MusiqaBot/cookies.txt). Run the bot:python3 main.py 
Usage Start the bot in Telegram with /start. Send a YouTube video link or song name to download audio. Send an Instagram reel 
link to download the video. Dependencies
   See requirements.txt for a full list of Python packages. Key dependencies include: python-telegram-bot 
google-api-python-client yt-dlp instaloader aiofiles python-dotenv aiohttp Notes Ensure the Instagram reel is public to avoid 
LoginRequiredException. The bot logs errors and activities to bot.log (excluded from Git via .gitignore). Temporary files 
(audio_*.info.json, media_*) are generated during downloads and excluded from Git. For deployment on AWS EC2, update the 
cookies.txt path in main.py and configure Supervisor. License
   This project is licensed under the MIT License.
