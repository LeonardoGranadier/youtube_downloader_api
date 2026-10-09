from fastapi import APIRouter, HTTPException

from pathlib import Path
from config import DOWNLOAD_DIR

from database.database import (get_download, get_downloads, delete_download,)

router = APIRouter(
    prefix="/downloads",
    tags=["Downloads"],
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

    # Remove o arquivo físico, se existir
    filepath = download.get("filepath")
    if filepath:
        base_dir = DOWNLOAD_DIR.resolve()
        file_path = Path(filepath).resolve()

    try:
        file_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Caminho de arquivo fora da pasta de downloads.",
        )

    if file_path.exists() and file_path.is_file():
        file_path.unlink()

    # Remove o registro do banco
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