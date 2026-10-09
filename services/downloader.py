import logging
from pathlib import Path
from typing import Callable, Optional

import yt_dlp
from yt_dlp.utils import match_filter_func

from config import (
    DOWNLOAD_DIR,
    MAX_DURATION_SECONDS,
    MAX_FILESIZE_MB,
)
from services.url_policy import (
    MediaError,
    get_allowed_extractors,
    validate_media_url,
)


logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[dict], None]]


# Teto de 1080p: resoluções maiores geram arquivos grandes demais
# para um serviço público (disco e tráfego de saída).
QUALITY_MAP = {
    "360": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "best": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
}


def _base_options() -> dict:
    """
    Opções de segurança comuns a toda chamada do yt-dlp.
    """

    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,

        # Só os extratores dos sites permitidos; nunca o "generic".
        "allowed_extractors": get_allowed_extractors(),

        # Bloqueia transmissões ao vivo e vídeos longos demais.
        # "<=?" deixa passar quando a duração é desconhecida.
        "match_filter": match_filter_func(
            f"!is_live & duration <=? {MAX_DURATION_SECONDS}"
        ),

        "max_filesize": MAX_FILESIZE_MB * 1024 * 1024,

        "socket_timeout": 30,
    }


def _run(options: dict, url: str, download: bool) -> dict:
    """
    Executa o yt-dlp convertendo qualquer falha em uma
    mensagem genérica. O detalhe técnico vai só para o log.
    """

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                url,
                download=download,
            )
    except Exception:
        logger.exception("Falha no yt-dlp para %s", url)

        raise MediaError(
            "Não foi possível processar este link. "
            "Verifique se o vídeo é público e permite download."
        )

    if info is None:
        raise MediaError("Não foi possível obter informações do vídeo.")

    return info


def _check_duration(info: dict) -> None:
    if info.get("is_live"):
        raise MediaError("Transmissões ao vivo não são suportadas.")

    duration = info.get("duration")

    if duration and duration > MAX_DURATION_SECONDS:
        raise MediaError(
            "Vídeo longo demais. Limite: "
            f"{MAX_DURATION_SECONDS // 60} minutos."
        )


def get_video_info(url: str) -> dict:
    """
    Obtém informações do vídeo sem realizar o download.
    """

    url = validate_media_url(url)

    options = _base_options()
    options["skip_download"] = True

    # O match_filter faria o yt-dlp pular o vídeo sem explicar o
    # motivo; aqui a duração é validada com mensagem clara.
    del options["match_filter"]

    info = _run(options, url, download=False)

    _check_duration(info)

    formats = info.get("formats") or []

    heights = sorted(
        {
            int(fmt["height"])
            for fmt in formats
            if fmt.get("height")
            and fmt.get("vcodec") != "none"
            and int(fmt["height"]) <= 1080
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


def _find_output(download_id: str, extension: str | None = None) -> Path:
    """
    Localiza o arquivo final pelo ID do download.

    Arquivos temporários do yt-dlp (.part, .ytdl) são ignorados.
    """

    pattern = f"{download_id}.{extension}" if extension else f"{download_id}.*"

    candidates = [
        path
        for path in DOWNLOAD_DIR.glob(pattern)
        if path.is_file()
        and path.suffix not in {".part", ".ytdl"}
    ]

    if not candidates:
        # Sem arquivo e sem erro: normalmente o yt-dlp pulou o download
        # por ultrapassar o max_filesize.
        raise MediaError(
            "O arquivo ultrapassa o limite de "
            f"{MAX_FILESIZE_MB} MB ou não pôde ser baixado."
        )

    return max(
        candidates,
        key=lambda item: item.stat().st_mtime,
    )


def download_video(
    download_id: str,
    url: str,
    quality: str = "best",
    progress_callback: ProgressCallback = None,
) -> Path:

    if quality not in QUALITY_MAP:
        raise MediaError("Qualidade inválida.")

    url = validate_media_url(url)

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    options = _base_options()

    options.update(
        {
            "format": QUALITY_MAP[quality],

            # Nome pelo ID, nunca pelo título: evita que dois usuários
            # baixando o mesmo vídeo sobrescrevam o arquivo um do outro.
            "outtmpl": str(DOWNLOAD_DIR / f"{download_id}.%(ext)s"),

            "merge_output_format": "mp4",

            "progress_hooks": [progress_callback] if progress_callback else [],
        }
    )

    info = _run(options, url, download=True)

    _check_duration(info)

    return _find_output(download_id)


def download_audio(
    download_id: str,
    url: str,
    progress_callback: ProgressCallback = None,
) -> Path:

    url = validate_media_url(url)

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    options = _base_options()

    options.update(
        {
            # Sem trilha de áudio separada, baixa um vídeo pequeno só
            # para extrair o áudio, nunca o de maior resolução.
            "format": "bestaudio/best[height<=480]/best",

            "outtmpl": str(DOWNLOAD_DIR / f"{download_id}.%(ext)s"),

            "progress_hooks": [progress_callback] if progress_callback else [],

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
    )

    info = _run(options, url, download=True)

    _check_duration(info)

    return _find_output(download_id, "mp3")
