import asyncio
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yt_dlp

from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DOWNLOAD_DIR = BASE_DIR / "downloads"
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "app.db"

DOWNLOAD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


app = FastAPI(
    title="YouTube Downloader V2",
    version="2.0.0",
)


app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


# ============================================================
# BANCO DE DADOS
# ============================================================

def get_connection():
    connection = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT,
            uploader TEXT,
            thumbnail TEXT,
            media_type TEXT NOT NULL,
            quality TEXT,
            status TEXT NOT NULL,
            progress REAL DEFAULT 0,
            speed TEXT,
            eta TEXT,
            filename TEXT,
            filepath TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )

    connection.commit()
    connection.close()


init_database()


# ============================================================
# MEMÓRIA TEMPORÁRIA DAS TAREFAS
# ============================================================

active_tasks = {}

download_locks = {}


# ============================================================
# UTILITÁRIOS
# ============================================================

def now():
    return datetime.now().isoformat(timespec="seconds")


def safe_filename(name: str):

    name = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        name,
    )

    name = re.sub(
        r"\s+",
        " ",
        name,
    )

    return name[:180].strip() or "video"


def update_database(download_id, **fields):

    if not fields:
        return

    connection = get_connection()

    columns = ", ".join(
        f"{key} = ?"
        for key in fields
    )

    values = list(fields.values())

    values.append(download_id)

    connection.execute(
        f"""
        UPDATE downloads
        SET {columns}
        WHERE id = ?
        """,
        values,
    )

    connection.commit()
    connection.close()


def get_download(download_id):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM downloads
        WHERE id = ?
        """,
        (download_id,),
    ).fetchone()

    connection.close()

    return dict(row) if row else None


def get_all_downloads():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM downloads
        ORDER BY created_at DESC
        """
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# PROGRESS HOOK
# ============================================================

def progress_hook(download_id):

    def hook(data):

        status = data.get("status")

        if status == "downloading":

            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
                or 0
            )

            downloaded = (
                data.get("downloaded_bytes")
                or 0
            )

            if total:
                percentage = (
                    downloaded / total
                ) * 100
            else:
                percentage = 0

            speed = data.get(
                "_speed_str",
                "",
            )

            eta = data.get(
                "_eta_str",
                "",
            )

            filename = Path(
                data.get("filename", "")
            ).name

            update_database(
                download_id,
                status="downloading",
                progress=round(
                    percentage,
                    1,
                ),
                speed=speed,
                eta=eta,
                filename=filename,
            )

        elif status == "finished":

            update_database(
                download_id,
                status="processing",
                progress=100,
                speed="",
                eta="",
            )

    return hook


# ============================================================
# FORMATOS
# ============================================================

QUALITY_MAP = {

    "360":
        "bestvideo[height<=360]+bestaudio/"
        "best[height<=360]",

    "480":
        "bestvideo[height<=480]+bestaudio/"
        "best[height<=480]",

    "720":
        "bestvideo[height<=720]+bestaudio/"
        "best[height<=720]",

    "1080":
        "bestvideo[height<=1080]+bestaudio/"
        "best[height<=1080]",

    "1440":
        "bestvideo[height<=1440]+bestaudio/"
        "best[height<=1440]",

    "2160":
        "bestvideo[height<=2160]+bestaudio/"
        "best[height<=2160]",

    "best":
        "bestvideo+bestaudio/best",
}


# ============================================================
# LOCALIZAR ARQUIVO FINAL
# ============================================================

def find_downloaded_file(
    title: str,
    media_type: str,
    before_timestamp: float,
):

    extensions = (
        {
            ".mp4",
            ".mkv",
            ".webm",
        }
        if media_type == "video"
        else {
            ".mp3",
            ".m4a",
            ".opus",
        }
    )

    title_safe = safe_filename(title).lower()

    candidates = []

    for file in DOWNLOAD_DIR.iterdir():

        if not file.is_file():
            continue

        if file.suffix.lower() not in extensions:
            continue

        try:
            stat = file.stat()
        except OSError:
            continue

        if stat.st_mtime < before_timestamp:
            continue

        if title_safe:
            file_name = file.stem.lower()

            if title_safe[:50] not in file_name:
                continue

        candidates.append(file)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


# ============================================================
# DOWNLOAD
# ============================================================

async def execute_download(download_id):

    record = get_download(download_id)

    if not record:
        return

    url = record["url"]
    quality = record["quality"] or "best"
    media_type = record["media_type"]

    before_timestamp = (
        datetime.now().timestamp()
    )

    try:

        update_database(
            download_id,
            status="starting",
            progress=0,
            error=None,
        )

        if media_type == "audio":

            format_selector = (
                "bestaudio/best"
            )

            postprocessors = [
                {
                    "key":
                        "FFmpegExtractAudio",

                    "preferredcodec":
                        "mp3",

                    "preferredquality":
                        "192",
                }
            ]

        else:

            format_selector = (
                QUALITY_MAP.get(
                    quality,
                    QUALITY_MAP["best"],
                )
            )

            postprocessors = []

        output_template = str(
            DOWNLOAD_DIR /
            "%(title)s.%(ext)s"
        )

        options = {

            "format":
                format_selector,

            "outtmpl":
                output_template,

            "noplaylist":
                True,

            "quiet":
                True,

            "no_warnings":
                True,

            "merge_output_format":
                "mp4"
                if media_type == "video"
                else None,

            "progress_hooks":
                [
                    progress_hook(
                        download_id
                    )
                ],

            "postprocessors":
                postprocessors,

            "restrictfilenames":
                False,

        }

        options = {
            key: value
            for key, value in options.items()
            if value is not None
        }

        def run():

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True,
                )

                return info

        info = await asyncio.to_thread(
            run
        )

        title = (
            info.get("title")
            or record["title"]
            or "download"
        )

        final_file = (
            find_downloaded_file(
                title,
                media_type,
                before_timestamp,
            )
        )

        if not final_file:

            raise FileNotFoundError(
                "O download terminou, "
                "mas o arquivo final não "
                "foi encontrado."
            )

        update_database(
            download_id,

            status="completed",

            progress=100,

            speed="",

            eta="",

            title=title,

            uploader=info.get(
                "uploader"
            ),

            thumbnail=info.get(
                "thumbnail"
            ),

            filename=final_file.name,

            filepath=str(final_file),

            completed_at=now(),

            error=None,
        )

    except Exception as error:

        update_database(
            download_id,

            status="error",

            error=str(error),

            speed="",

            eta="",
        )

    finally:

        active_tasks.pop(
            download_id,
            None,
        )

        download_locks.pop(
            download_id,
            None,
        )


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
async def index(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request
        },
    )


# ============================================================
# INFORMAÇÕES DO VÍDEO
# ============================================================

@app.post("/api/info")
async def video_info(
    url: str = Form(...),
):

    url = url.strip()

    if not url:

        return JSONResponse(
            {
                "error":
                    "Informe uma URL."
            },
            status_code=400,
        )

    try:

        options = {
            "quiet":
                True,

            "no_warnings":
                True,

            "skip_download":
                True,

            "noplaylist":
                True,
        }

        def extract():

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                return ydl.extract_info(
                    url,
                    download=False,
                )

        info = await asyncio.to_thread(
            extract
        )

        formats = []

        for item in (
            info.get("formats")
            or []
        ):

            height = item.get(
                "height"
            )

            if height:

                formats.append(
                    height
                )

        available_heights = sorted(
            set(formats),
            reverse=True,
        )

        return {

            "id":
                info.get("id"),

            "title":
                info.get("title"),

            "uploader":
                info.get("uploader"),

            "duration":
                info.get("duration"),

            "thumbnail":
                info.get("thumbnail"),

            "webpage_url":
                info.get(
                    "webpage_url"
                ),

            "available_heights":
                available_heights,

        }

    except Exception as error:

        return JSONResponse(
            {
                "error":
                    "Não foi possível "
                    "obter as informações: "
                    f"{error}"
            },
            status_code=400,
        )


# ============================================================
# CRIAR DOWNLOAD
# ============================================================

@app.post("/api/download")
async def create_download(

    url: str = Form(...),

    quality: str = Form("best"),

    media_type: str = Form("video"),

):

    url = url.strip()

    if not url:

        return JSONResponse(
            {
                "error":
                    "Informe uma URL."
            },
            status_code=400,
        )

    if media_type not in {
        "video",
        "audio",
    }:

        return JSONResponse(
            {
                "error":
                    "Tipo de mídia inválido."
            },
            status_code=400,
        )

    if quality not in QUALITY_MAP:

        quality = "best"

    download_id = str(
        uuid.uuid4()
    )

    created_at = now()

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO downloads (
            id,
            url,
            title,
            uploader,
            thumbnail,
            media_type,
            quality,
            status,
            progress,
            speed,
            eta,
            filename,
            filepath,
            error,
            created_at,
            completed_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            download_id,
            url,
            None,
            None,
            None,
            media_type,
            quality,
            "queued",
            0,
            "",
            "",
            None,
            None,
            None,
            created_at,
            None,
        ),
    )

    connection.commit()
    connection.close()

    task = asyncio.create_task(
        execute_download(
            download_id
        )
    )

    active_tasks[
        download_id
    ] = task

    return {
        "success":
            True,

        "download_id":
            download_id,
    }


# ============================================================
# PROGRESSO
# ============================================================

@app.get(
    "/api/progress/{download_id}"
)
async def download_progress(
    download_id: str,
):

    download = get_download(
        download_id
    )

    if not download:

        return JSONResponse(
            {
                "error":
                    "Download não encontrado."
            },
            status_code=404,
        )

    return download


# ============================================================
# HISTÓRICO
# ============================================================

@app.get("/api/history")
async def history():

    return {
        "downloads":
            get_all_downloads()
    }


# ============================================================
# ESTATÍSTICAS
# ============================================================

@app.get("/api/stats")
async def stats():

    connection = get_connection()

    total = connection.execute(
        """
        SELECT COUNT(*)
        FROM downloads
        """
    ).fetchone()[0]

    completed = connection.execute(
        """
        SELECT COUNT(*)
        FROM downloads
        WHERE status = 'completed'
        """
    ).fetchone()[0]

    errors = connection.execute(
        """
        SELECT COUNT(*)
        FROM downloads
        WHERE status = 'error'
        """
    ).fetchone()[0]

    connection.close()

    files = 0
    total_size = 0

    for file in DOWNLOAD_DIR.iterdir():

        if file.is_file():

            files += 1

            try:
                total_size += file.stat().st_size
            except OSError:
                pass

    return {

        "total":
            total,

        "completed":
            completed,

        "errors":
            errors,

        "files":
            files,

        "storage_bytes":
            total_size,

    }


# ============================================================
# BIBLIOTECA
# ============================================================

@app.get("/api/library")
async def library():

    files = []

    for file in DOWNLOAD_DIR.iterdir():

        if not file.is_file():
            continue

        try:

            stat = file.stat()

            files.append(
                {
                    "name":
                        file.name,

                    "size":
                        stat.st_size,

                    "modified":
                        datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(
                            timespec="seconds"
                        ),

                    "extension":
                        file.suffix.lower(),

                }
            )

        except OSError:
            continue

    files.sort(
        key=lambda item:
            item["modified"],
        reverse=True,
    )

    return {
        "files": files
    }


# ============================================================
# ARQUIVO
# ============================================================

@app.get("/api/file/{filename}")
async def get_file(
    filename: str
):

    safe_name = Path(
        filename
    ).name

    path = (
        DOWNLOAD_DIR /
        safe_name
    )

    if (
        not path.exists()
        or not path.is_file()
    ):

        return JSONResponse(
            {
                "error":
                    "Arquivo não encontrado."
            },
            status_code=404,
        )

    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
    )


# ============================================================
# EXCLUIR ARQUIVO
# ============================================================

@app.delete("/api/file/{filename}")
async def delete_file(
    filename: str
):

    safe_name = Path(
        filename
    ).name

    path = (
        DOWNLOAD_DIR /
        safe_name
    )

    if (
        not path.exists()
        or not path.is_file()
    ):

        return JSONResponse(
            {
                "error":
                    "Arquivo não encontrado."
            },
            status_code=404,
        )

    try:

        path.unlink()

    except Exception as error:

        return JSONResponse(
            {
                "error":
                    str(error)
            },
            status_code=500,
        )

    connection = get_connection()

    connection.execute(
        """
        UPDATE downloads
        SET filepath = NULL
        WHERE filename = ?
        """,
        (safe_name,),
    )

    connection.commit()
    connection.close()

    return {
        "success":
            True
    }


# ============================================================
# LIMPAR HISTÓRICO
# ============================================================

@app.delete("/api/history")
async def clear_history():

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM downloads
        """
    )

    connection.commit()
    connection.close()

    return {
        "success":
            True
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():

    init_database()

    connection = get_connection()

    connection.execute(
        """
        UPDATE downloads
        SET
            status = ?,
            error = ?
        WHERE status IN (
            'queued',
            'starting',
            'downloading',
            'processing'
        )
        """,
        (
            "error",
            "Download interrompido quando o servidor foi reiniciado.",
        ),
    )

    connection.commit()
    connection.close()