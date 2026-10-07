import subprocess
from pathlib import Path

from config import FFMPEG_PATH


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