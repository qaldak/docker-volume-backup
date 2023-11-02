import os

from dotenv import load_dotenv

# globals
hasError = False
errorMsg = ""

# load .env settings
load_dotenv()

backup_path = os.getenv("BACKUP_PATH")
chat_service = os.getenv("CHAT_SERVICE")
