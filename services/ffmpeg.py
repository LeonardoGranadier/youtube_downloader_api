import logging
import subprocess
from pathlib import Path

from config import FFMPEG_PATH, FFPROBE_PATH


logger = logging.getLogger(__name__)

# Codecs de vídeo que o contêiner MP4 aceita sem recodificar. Fora disso,
# a junção vai para MKV (aceita qualquer codec).
MP4_VIDEO_CODECS = {"h264", "hevc", "mpeg4", "av1", "vp9"}


def check_ffmpeg() -> bool:
    """
    Verifica se o FFmpeg está instalado e disponível.
    """

    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )

        return result.returncode == 0

    except (
        FileNotFoundError,
        subprocess.SubprocessError,
        OSError,
    ):
        return False


def get_ffmpeg_version() -> str | None:
    """
    Retorna a versão do FFmpeg instalada.
    """

    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return None

        first_line = result.stdout.splitlines()[0]

        return first_line

    except (
        FileNotFoundError,
        subprocess.SubprocessError,
        OSError,
    ):
        return None


def convert_to_mp3(
    input_file: Path,
    output_file: Path,
) -> None:
    """
    Converte um arquivo de mídia para MP3.
    """

    command = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(input_file),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(output_file),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg falhou ao converter o arquivo: "
            f"{result.stderr[-2000:]}"
        )


def remove_file(file_path: Path) -> None:
    """
    Remove um arquivo se ele existir.
    """

    if file_path.exists():
        file_path.unlink()


def _probe(file_path: Path, stream: str, entry: str) -> list[str]:
    """
    Lê um campo dos streams de um tipo ("a" ou "v") do arquivo real.
    Lista de argumentos fixa, nunca string de shell.
    """

    result = subprocess.run(
        [
            FFPROBE_PATH,
            "-v", "error",
            "-select_streams", stream,
            "-show_entries", f"stream={entry}",
            "-of", "csv=p=0",
            str(file_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {result.stderr[-500:]}")

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def has_audio_stream(file_path: Path) -> bool:
    """
    Confere no arquivo de verdade se existe faixa de áudio. Os metadados
    do site nem sempre dizem (archive.org informa codec "unknown").
    """

    return bool(_probe(file_path, "a", "codec_name"))


def video_codec(file_path: Path) -> str | None:
    codecs = _probe(file_path, "v", "codec_name")

    return codecs[0] if codecs else None


def merge_video_audio(
    video_file: Path,
    audio_file: Path,
    output_base: Path,
) -> Path:
    """
    Junta o vídeo de um arquivo com o áudio de outro, sem recodificar o
    vídeo. Saída MP4 (áudio em AAC) quando o codec permite; senão MKV.

    output_base é o caminho sem extensão.
    """

    codec = video_codec(video_file)

    if codec in MP4_VIDEO_CODECS:
        output_file = output_base.with_suffix(".mp4")
        codec_args = ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    else:
        output_file = output_base.with_suffix(".mkv")
        codec_args = ["-c", "copy"]

    command = [
        FFMPEG_PATH,
        "-y",
        "-i", str(video_file),
        "-i", str(audio_file),
        "-map", "0:v:0",
        "-map", "1:a:0",
        *codec_args,
        "-shortest",
        str(output_file),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        output_file.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg falhou ao juntar vídeo e áudio: {result.stderr[-2000:]}")

    return output_file

