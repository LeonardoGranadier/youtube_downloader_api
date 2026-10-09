import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from config import (
    CLEANUP_INTERVAL_SECONDS,
    DOWNLOAD_DIR,
    FILE_TTL_MINUTES,
    MAX_CONCURRENT_DOWNLOADS,
)

from database.database import (
    create_download as create_download_record,
    delete_download,
    get_expired_downloads,
    update_download,
)
from services.downloader import (get_video_info,download_audio, download_video)
from services.queue import DownloadQueue
from services.url_policy import MediaError


logger = logging.getLogger(__name__)


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

    # Valida domínio e duração antes de entrar na fila.
    # Um MediaError aqui vira 400 para o cliente.
    info = await asyncio.to_thread(
        get_video_info,
        url,
    )

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
                    download_id,
                    url,
                    progress_callback,
                )
            else:
                file_path = await asyncio.to_thread(
                    download_video,
                    download_id,
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
            # Só mensagens de MediaError são seguras para o usuário;
            # qualquer outra falha fica registrada apenas no log.
            if isinstance(error, MediaError):
                message = str(error)
            else:
                logger.exception("Falha no download %s", download_id)
                message = "Não foi possível concluir o download."

            update_download(
                download_id,
                status="error",
                error=message,
                completed_at=utc_now(),
            )

            # O erro já está registrado no banco; ninguém aguarda este
            # future, então relançar só geraria "exception never retrieved".
            return {
                "id": download_id,
                "status": "error",
            }

    future = await download_queue.add(
        task_id=download_id,
        function=process_download,
    )

    return {
        "id": download_id,
        "status": "queued",
        "future": future,
    }

def remove_download_files(download_id: str) -> None:
    """
    Remove o arquivo final e eventuais temporários do download.
    """

    for path in DOWNLOAD_DIR.glob(f"{download_id}.*"):
        if path.is_file():
            path.unlink(missing_ok=True)


def cleanup_expired() -> int:
    """
    Apaga downloads concluídos ou com erro mais antigos que o TTL,
    além de arquivos órfãos na pasta de downloads.
    """

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=FILE_TTL_MINUTES)

    removed = 0

    for download_id in get_expired_downloads(cutoff.isoformat()):
        remove_download_files(download_id)
        delete_download(download_id)
        removed += 1

    # Arquivos sem registro no banco (ex.: restart no meio do download).
    for path in DOWNLOAD_DIR.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue

        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)

        if modified < cutoff:
            path.unlink(missing_ok=True)

    return removed


async def cleanup_loop() -> None:
    while True:
        try:
            removed = await asyncio.to_thread(cleanup_expired)

            if removed:
                logger.info("Limpeza: %s downloads expirados removidos", removed)

        except Exception:
            logger.exception("Falha na limpeza de downloads")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
