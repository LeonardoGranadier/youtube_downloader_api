import asyncio

from fastapi import APIRouter, HTTPException, Depends

from security import require_api_key

from schemas.youtube import (
    YouTubeInfoRequest,
    YouTubeInfoResponse,
    YouTubeDownloadRequest,
)

from services.downloader import get_video_info
from services.download_manager import create_download


router = APIRouter(
    prefix="/youtube",
    tags=["YouTube"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/info",
    response_model=YouTubeInfoResponse,
)
async def youtube_info(
    request: YouTubeInfoRequest,
):
    try:
        info = await asyncio.to_thread(
            get_video_info,
            request.url,
)

        return YouTubeInfoResponse(
            **info
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@router.post(
    "/download",
)
async def youtube_download(
    request: YouTubeDownloadRequest,
):
    if request.media_type not in {
        "video",
        "audio",
    }:
        raise HTTPException(
            status_code=400,
            detail="media_type deve ser 'video' ou 'audio'.",
        )

    if request.media_type == "video":
        valid_qualities = {
            "360",
            "480",
            "720",
            "1080",
            "1440",
            "2160",
            "best",
        }

        if request.quality not in valid_qualities:
            raise HTTPException(
                status_code=400,
                detail="Qualidade inválida.",
            )

    try:
        result = await create_download(
            url=request.url,
            media_type=request.media_type,
            quality=request.quality,
        )

        return {
            "id": result["id"],
            "status": result["status"],
            "message": "Download adicionado à fila.",
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )