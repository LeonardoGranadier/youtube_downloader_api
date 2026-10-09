from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from config import DOWNLOAD_DIR
from security import require_api_key


router = APIRouter(
    prefix="/files",
    tags=["Files"],
    dependencies=[Depends(require_api_key)],
)


def get_safe_file_path(filename: str) -> Path:
    base_dir = DOWNLOAD_DIR.resolve()
    file_path = (DOWNLOAD_DIR / filename).resolve()

    try:
        file_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Caminho de arquivo inválido.",
        )

    return file_path


@router.get("")
async def list_files():
    files = []

    for file_path in DOWNLOAD_DIR.iterdir():
        if not file_path.is_file():
            continue

        files.append(
            {
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "path": str(file_path),
            }
        )

    return files


@router.get("/{filename}")
async def get_file(filename: str):
    file_path = get_safe_file_path(filename)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Arquivo não encontrado.",
        )

    return FileResponse(
        path=file_path,
        filename=file_path.name,
    )


@router.delete("/{filename}")
async def delete_file(filename: str):
    file_path = get_safe_file_path(filename)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Arquivo não encontrado.",
        )

    file_path.unlink()

    return {
        "message": "Arquivo removido com sucesso.",
        "filename": filename,
    }