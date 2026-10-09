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
from services.ffmpeg import has_audio_stream, merge_video_audio
from services.url_policy import (
    MediaError,
    get_allowed_extractors,
    validate_media_url,
)


logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[dict], None]]


# Teto de 1080p: resoluções maiores geram arquivos grandes demais
# para um serviço público (disco e tráfego de saída).
MAX_HEIGHT = 1080


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

    heights = sorted(
        {
            int(fmt["height"])
            for fmt in _video_formats(info.get("formats") or [])
            if int(fmt["height"]) <= MAX_HEIGHT
        }
    )

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "thumbnail": _safe_thumbnail(info.get("thumbnail")),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
        "available_heights": heights,
    }


def _safe_thumbnail(url: str | None) -> str | None:
    """
    A miniatura é carregada pelo navegador do usuário: só repassa se for
    HTTPS de um dos próprios sites permitidos.
    """

    if not url:
        return None

    try:
        validate_media_url(url)
    except MediaError:
        return None

    return url


def _video_formats(formats: list[dict]) -> list[dict]:
    # archive.org informa vcodec "unknown": conta como vídeo se tiver altura.
    return [
        fmt
        for fmt in formats
        if fmt.get("height")
        and fmt.get("vcodec") != "none"
    ]


def _may_have_audio(fmt: dict) -> bool:
    # "none" é certeza de que não tem; "unknown"/ausente pode ter (o
    # arquivo baixado é conferido com ffprobe depois).
    return fmt.get("acodec") != "none"


def _size(fmt: dict) -> float:
    return fmt.get("filesize") or fmt.get("filesize_approx") or fmt.get("tbr") or 0


def pick_video_format(formats: list[dict], quality: str) -> dict:
    """
    Escolhe o formato de vídeo na altura exata pedida ("best" = a maior
    até 1080p). Entre empates, prefere o que já tem áudio.
    """

    videos = [
        fmt
        for fmt in _video_formats(formats)
        if int(fmt["height"]) <= MAX_HEIGHT
    ]

    if not videos:
        raise MediaError("Nenhuma versão de vídeo disponível até 1080p.")

    if quality == "best":
        target = max(int(fmt["height"]) for fmt in videos)
    else:
        target = int(quality)

    candidates = [fmt for fmt in videos if int(fmt["height"]) == target]

    if not candidates:
        raise MediaError(f"Qualidade {target}p não disponível para este vídeo.")

    return max(
        candidates,
        key=lambda fmt: (_may_have_audio(fmt), _size(fmt)),
    )


def pick_audio_donor(formats: list[dict], exclude_id: str) -> dict | None:
    """
    De onde tirar o som quando o vídeo escolhido vem mudo: de preferência
    uma faixa só de áudio; senão, a versão mais leve que tenha áudio.
    """

    with_audio = [
        fmt
        for fmt in formats
        if fmt.get("format_id") != exclude_id
        and _may_have_audio(fmt)
        and fmt.get("acodec")
    ]

    if not with_audio:
        # Sem informação de codec (archive.org): qualquer outra versão
        # pode ter áudio; o arquivo é conferido com ffprobe depois.
        with_audio = [
            fmt
            for fmt in formats
            if fmt.get("format_id") != exclude_id
            and _may_have_audio(fmt)
        ]

    if not with_audio:
        return None

    audio_only = [fmt for fmt in with_audio if fmt.get("vcodec") == "none"]

    if audio_only:
        return max(audio_only, key=_size)

    return min(with_audio, key=_size)


def _scaled_progress(
    callback: ProgressCallback,
    start: float,
    end: float,
) -> Callable[[dict], None] | None:
    """
    Converte o progresso de uma etapa (0-100%) para a faixa start-end do
    download inteiro. O "finished" de cada etapa é segurado: quem avisa
    o fim é download_video, depois de todas as etapas.
    """

    if callback is None:
        return None

    def hook(data: dict) -> None:
        if data.get("status") != "downloading":
            return

        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        done = data.get("downloaded_bytes")

        if not total or done is None:
            return

        fraction = min(done / total, 1.0)

        callback(
            {
                **data,
                "_percent_str": f"{start + (end - start) * fraction:.1f}%",
            }
        )

    return hook


def _download_format(
    download_id: str,
    part: str,
    url: str,
    format_selector: str,
    progress_hook: Callable[[dict], None] | None,
) -> Path:
    """
    Baixa um formato específico para "<id>.<part>.<ext>".
    """

    options = _base_options()

    options.update(
        {
            "format": format_selector,

            # Nome pelo ID, nunca pelo título: evita que dois usuários
            # baixando o mesmo vídeo sobrescrevam o arquivo um do outro.
            "outtmpl": str(DOWNLOAD_DIR / f"{download_id}.{part}.%(ext)s"),

            # Quando o próprio yt-dlp junta vídeo + faixa de áudio separada.
            "merge_output_format": "mp4/mkv",

            "progress_hooks": [progress_hook] if progress_hook else [],
        }
    )

    info = _run(options, url, download=True)

    _check_duration(info)

    for item in info.get("requested_downloads") or []:
        path = Path(item.get("filepath") or "")

        if path.is_file():
            return path

    candidates = [
        path
        for path in DOWNLOAD_DIR.glob(f"{download_id}.{part}.*")
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

    return candidates[0]


def _check_final_size(path: Path) -> None:
    if path.stat().st_size > MAX_FILESIZE_MB * 1024 * 1024:
        path.unlink(missing_ok=True)

        raise MediaError(
            "O arquivo ultrapassa o limite de "
            f"{MAX_FILESIZE_MB} MB."
        )


def download_video(
    download_id: str,
    url: str,
    quality: str = "best",
    progress_callback: ProgressCallback = None,
) -> Path:
    """
    Baixa o vídeo na resolução pedida e garante que ele venha com som:
    se a versão escolhida for muda, baixa o áudio de outra versão e junta
    com FFmpeg (sem recodificar o vídeo).
    """

    url = validate_media_url(url)

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    options = _base_options()
    options["skip_download"] = True
    del options["match_filter"]

    info = _run(options, url, download=False)

    _check_duration(info)

    formats = info.get("formats") or []

    video = pick_video_format(formats, quality)
    video_id = video["format_id"]

    audio_only = [
        fmt
        for fmt in formats
        if fmt.get("vcodec") == "none"
        and fmt.get("acodec") not in (None, "none")
    ]

    temp_files: list[Path] = []
    finished_sent = False

    try:
        if not _may_have_audio(video) and audio_only:
            # Caso comum: o próprio yt-dlp junta vídeo + faixa de áudio.
            selector = f"{video_id}+{max(audio_only, key=_size)['format_id']}"
            video_span = (0.0, 100.0)
        else:
            selector = video_id
            video_span = (0.0, 85.0)

        video_path = _download_format(
            download_id,
            "video",
            url,
            selector,
            _scaled_progress(progress_callback, *video_span),
        )
        temp_files.append(video_path)

        result_path = video_path

        if not has_audio_stream(video_path):
            donor = pick_audio_donor(formats, exclude_id=video_id)

            if donor is not None:
                audio_path = _download_format(
                    download_id,
                    "audio",
                    url,
                    donor["format_id"],
                    _scaled_progress(progress_callback, 85.0, 100.0),
                )
                temp_files.append(audio_path)

                if has_audio_stream(audio_path):
                    # Avisa o fim do download antes da junção (status
                    # "processing" enquanto o FFmpeg trabalha).
                    if progress_callback:
                        progress_callback({"status": "finished"})
                        finished_sent = True

                    try:
                        result_path = merge_video_audio(
                            video_path,
                            audio_path,
                            DOWNLOAD_DIR / download_id,
                        )
                    except RuntimeError:
                        logger.exception("Falha ao juntar vídeo e áudio (%s)", download_id)

                        raise MediaError("Não foi possível juntar o vídeo com o áudio.")

            # Sem nenhuma versão com som: o vídeo original é mudo.

        if progress_callback and not finished_sent:
            progress_callback({"status": "finished"})

        if result_path == video_path:
            final_path = DOWNLOAD_DIR / f"{download_id}{video_path.suffix}"
            video_path.rename(final_path)
            temp_files.remove(video_path)
            result_path = final_path

        _check_final_size(result_path)

        return result_path

    finally:
        for path in temp_files:
            path.unlink(missing_ok=True)


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

    path = DOWNLOAD_DIR / f"{download_id}.mp3"

    if not path.is_file():
        raise MediaError(
            "O arquivo ultrapassa o limite de "
            f"{MAX_FILESIZE_MB} MB ou não pôde ser baixado."
        )

    return path
