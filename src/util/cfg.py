import os

from dotenv import load_dotenv

# globals
hasWarnings = False
warningMsg = ""
hasError = False
errorMsg = ""

# load .env settings
load_dotenv()

backup_path = os.getenv("BACKUP_PATH")
slack_token = os.getenv("SLACK_TOKEN")
