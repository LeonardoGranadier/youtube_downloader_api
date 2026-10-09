import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from config import DOWNLOAD_DIR
from database.database import (
    get_download,
    get_downloads,
    delete_download,
)
from security import require_api_key


router = APIRouter(
    prefix="/downloads",
    tags=["Downloads"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
async def list_downloads():
    return get_downloads()


@router.get("/{download_id}")
async def download_details(
    download_id: str,
):
    download = get_download(download_id)

    if download is None:
        raise HTTPException(
            status_code=404,
            detail="Download não encontrado.",
        )

    return download


@router.get("/{download_id}/progress")
async def download_progress(
    download_id: str,
):
    download = get_download(download_id)

    if download is None:
        raise HTTPException(
            status_code=404,
            detail="Download não encontrado.",
        )

    return {
        "id": download["id"],
        "status": download["status"],
        "progress": download["progress"],
        "speed": download["speed"],
        "eta": download["eta"],
    }


def friendly_filename(title: str | None, extension: str) -> str:
    """
    Nome de arquivo amigável para o usuário, derivado do título.
    O arquivo em disco continua nomeado pelo ID do download.
    """

    name = re.sub(r"[^\w\s.-]", "", title or "", flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip(" .")[:120]

    return f"{name or 'video'}{extension}"


@router.get("/{download_id}/file")
async def download_file(
    download_id: str,
):
    download = get_download(download_id)

    if download is None or download["status"] != "completed":
        raise HTTPException(
            status_code=404,
            detail="Arquivo não disponível.",
        )

    base_dir = DOWNLOAD_DIR.resolve()
    file_path = Path(download["filepath"] or "").resolve()

    try:
        file_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Arquivo não disponível.",
        )

    if not file_path.is_file():
        # Já removido pela limpeza automática.
        raise HTTPException(
            status_code=404,
            detail="Arquivo não disponível.",
        )

    return FileResponse(
        path=file_path,
        filename=friendly_filename(download["title"], file_path.suffix),
    )


@router.delete("/{download_id}")
async def delete_download_item(
    download_id: str,
):
    download = get_download(download_id)

    if download is None:
        raise HTTPException(
            status_code=404,
            detail="Download não encontrado.",
        )

    if download["status"] in {
        "queued",
        "starting",
        "downloading",
        "processing",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Não é possível excluir um download "
                "que está na fila ou em execução."
            ),
        )

    # Remove o arquivo físico, se existir.
    filepath = download.get("filepath")

    if filepath:
        base_dir = DOWNLOAD_DIR.resolve()
        file_path = Path(filepath).resolve()

        # Impede a exclusão de arquivos fora da pasta permitida.
        try:
            file_path.relative_to(base_dir)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Caminho de arquivo fora "
                    "da pasta de downloads."
                ),
            )

        if file_path.exists() and file_path.is_file():
            file_path.unlink()

    # Remove o registro do banco de dados.
    deleted = delete_download(download_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Download não encontrado.",
        )

    return {
        "message": "Download removido com sucesso.",
        "id": download_id,
    }