import asyncio

from fastapi import APIRouter, HTTPException, Depends

from security import require_api_key

from schemas.media import (
    MediaInfoRequest,
    MediaInfoResponse,
    MediaDownloadRequest,
)

from services.downloader import get_video_info
from services.download_manager import create_download
from services.url_policy import MediaError


router = APIRouter(
    prefix="/media",
    tags=["Media"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/info",
    response_model=MediaInfoResponse,
)
async def media_info(
    request: MediaInfoRequest,
):
    try:
        info = await asyncio.to_thread(
            get_video_info,
            request.url,
        )

    except MediaError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return MediaInfoResponse(
        **info
    )


@router.post(
    "/download",
    status_code=202,
)
async def media_download(
    request: MediaDownloadRequest,
):
    # A qualidade não se aplica a áudio; o tipo e a qualidade
    # já foram validados pelo schema (Literal).
    try:
        result = await create_download(
            url=request.url,
            media_type=request.media_type,
            quality=request.quality,
        )

    except MediaError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return {
        "id": result["id"],
        "status": result["status"],
        "message": "Download adicionado à fila.",
    }
