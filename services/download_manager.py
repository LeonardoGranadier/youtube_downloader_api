import asyncio
import re
import uuid
from datetime import datetime, timezone

from config import MAX_CONCURRENT_DOWNLOADS

from database.database import (create_download as create_download_record, update_download,)
from services.downloader import (get_video_info,download_audio, download_video)
from services.queue import DownloadQueue


download_queue = DownloadQueue(
    max_concurrent=MAX_CONCURRENT_DOWNLOADS
)

ANSI_ESCAPE_PATTERN = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)


def clean_ansi(value):
    if value is None:
        return None

    return ANSI_ESCAPE_PATTERN.sub(
        "",
        str(value),
    ).strip()


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


async def start_queue():
    await download_queue.start()


async def stop_queue():
    await download_queue.stop()


async def create_download(
    url: str,
    media_type: str = "video",
    quality: str = "best",
):
    download_id = str(uuid.uuid4())

    created_at = utc_now()

    try: 
        info = await asyncio.to_thread(
            get_video_info,
            url,
        )
    except Exception:
        info = {}

    create_download_record(
        download_id,
        url=url,
        title=info.get("title"),
        uploader=info.get("uploader"),
        thumbnail=info.get("thumbnail"),
        media_type=media_type,
        quality=quality,
        status="queued",
        progress=0,
        created_at=created_at,
    )

    async def process_download():
        update_download(
            download_id,
            status="starting",
        )

        def progress_callback(data: dict):
            status = data.get("status")

            if status == "downloading":
                percent = data.get(
                    "_percent_str"
                )

                speed = clean_ansi(
                    data.get("_speed_str")
                )

                eta = clean_ansi(
                    data.get("_eta_str")
                )

                try:
                    progress = float(
                        percent
                        .replace("%", "")
                        .strip()
                    )
                except (
                    AttributeError,
                    ValueError,
                ):
                    progress = 0

                update_download(
                    download_id,
                    status="downloading",
                    progress=progress,
                    speed=speed,
                    eta=eta,
                )

            elif status == "finished":
                update_download(
                    download_id,
                    status="processing",
                    progress=100,
                )

        try:
            if media_type == "audio":
                file_path = await asyncio.to_thread(
                    download_audio,
                    url,
                    progress_callback,
                )
            else:
                file_path = await asyncio.to_thread(
                    download_video,
                    url,
                    quality,
                    progress_callback,
                )

            update_download(
                download_id,
                status="completed",
                progress=100,
                filename=file_path.name,
                filepath=str(file_path),
                completed_at=utc_now(),
            )

            return {
                "id": download_id,
                "status": "completed",
                "filename": file_path.name,
            }

        except Exception as error:
            update_download(
                download_id,
                status="error",
                error=str(error),
            )

            raise

    future = await download_queue.add(
        task_id=download_id,
        function=process_download,
    )

    return {
        "id": download_id,
        "status": "queued",
        "future": future,
    }