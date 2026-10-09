from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DOWNLOAD_DIR = BASE_DIR / "downloads"
DATA_DIR = BASE_DIR / "data"

DATABASE_PATH = DATA_DIR / "app.db"

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg")

API_PREFIX = "/api/v1"
# Autenticação da API
MEDIA_API_KEY = os.getenv("MEDIA_API_KEY", "")

def get_max_concurrent_downloads() -> int:
    value = os.getenv(
        "MAX_CONCURRENT_DOWNLOADS",
        "2",
    )

    try:
        value = int(value)
    except ValueError:
        return 2

    if value < 1:
        return 2

    return value


MAX_CONCURRENT_DOWNLOADS = get_max_concurrent_downloads()

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
