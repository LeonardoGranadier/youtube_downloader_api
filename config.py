from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent

DOWNLOAD_DIR = BASE_DIR / "downloads"
DATA_DIR = BASE_DIR / "data"

DATABASE_PATH = DATA_DIR / "app.db"

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg")

API_PREFIX = "/api/v1"

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
