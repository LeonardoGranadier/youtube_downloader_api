from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from config import DOWNLOAD_DIR


ProgressCallback = Optional[Callable[[dict], None]]


QUALITY_MAP = {
    "360": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "1440": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "2160": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "best": "bestvideo+bestaudio/best",
}


def get_video_info(url: str) -> dict:
    """
    Obtém informações do vídeo sem realizar o download.
    """

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=False,
        )

    if info is None:
        raise RuntimeError(
            "Não foi possível obter informações do vídeo."
        )

    formats = info.get("formats") or []

    heights = sorted(
        {
            int(fmt["height"])
            for fmt in formats
            if fmt.get("height")
            and fmt.get("vcodec") != "none"
        }
    )

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
        "available_heights": heights,
    }


def _default_progress(data: dict) -> None:
    """
    Callback padrão para progresso.
    """

    status = data.get("status")

    if status == "downloading":
        percent = data.get("_percent_str")
        speed = data.get("_speed_str")
        eta = data.get("_eta_str")

        print(
            f"Download: {percent} | "
            f"Velocidade: {speed} | "
            f"ETA: {eta}"
        )

    elif status == "finished":
        print("Download concluído. Processando arquivo...")


def download_video(
    url: str,
    quality: str = "best",
    progress_callback: ProgressCallback = None,
) -> Path:

    if quality not in QUALITY_MAP:
        raise ValueError(
            f"Qualidade inválida: {quality}"
        )

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    callback = (
        progress_callback
        if progress_callback is not None
        else _default_progress
    )

    options = {
        "format": QUALITY_MAP[quality],

        "outtmpl": str(
            DOWNLOAD_DIR / "%(title)s.%(ext)s"
        ),

        "merge_output_format": "mp4",

        "noplaylist": True,

        "quiet": True,

        "no_warnings": True,

        "restrictfilenames": False,

        "progress_hooks": [callback],
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=True,
        )

        if info is None:
            raise RuntimeError(
                "O yt-dlp não retornou informações do vídeo."
            )

        filename = ydl.prepare_filename(info)

    path = Path(filename)

    # Quando vídeo e áudio são mesclados pelo FFmpeg,
    # o arquivo final normalmente será MP4.
    if path.suffix.lower() != ".mp4":

        possible_mp4 = path.with_suffix(".mp4")

        if possible_mp4.exists():
            path = possible_mp4

    if not path.exists():

        title = info.get("title")

        if title:
            candidates = list(
                DOWNLOAD_DIR.glob(
                    f"{title}.*"
                )
            )

            if candidates:
                path = max(
                    candidates,
                    key=lambda item: item.stat().st_mtime,
                )

    if not path.exists():
        raise FileNotFoundError(
            "O download terminou, mas o arquivo final "
            "não foi localizado."
        )

    return path


def download_audio(
    url: str,
    progress_callback: ProgressCallback = None,
) -> Path:

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    callback = (
        progress_callback
        if progress_callback is not None
        else _default_progress
    )

    options = {
        "format": "bestaudio/best",

        "outtmpl": str(
            DOWNLOAD_DIR / "%(title)s.%(ext)s"
        ),

        "noplaylist": True,

        "quiet": True,

        "no_warnings": True,

        "restrictfilenames": False,

        "progress_hooks": [callback],

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=True,
        )

        if info is None:
            raise RuntimeError(
                "O yt-dlp não retornou informações do áudio."
            )

        filename = ydl.prepare_filename(info)

    original_path = Path(filename)

    mp3_path = original_path.with_suffix(".mp3")

    if mp3_path.exists():
        return mp3_path

    title = info.get("title")

    if title:
        candidates = list(
            DOWNLOAD_DIR.glob(
                f"{title}.mp3"
            )
        )

        if candidates:
            return max(
                candidates,
                key=lambda item: item.stat().st_mtime,
            )

    raise FileNotFoundError(
        "O áudio foi processado, mas o arquivo MP3 "
        "não foi localizado."
    )