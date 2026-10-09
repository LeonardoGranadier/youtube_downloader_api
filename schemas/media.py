from typing import Literal

from pydantic import BaseModel, Field


class MediaInfoRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=5,
        max_length=2048,
        description="URL do vídeo (somente sites permitidos)",
    )


class MediaInfoResponse(BaseModel):
    id: str | None = None
    title: str | None = None
    uploader: str | None = None
    thumbnail: str | None = None
    duration: float | None = None
    webpage_url: str | None = None
    available_heights: list[int] = []


class MediaDownloadRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=5,
        max_length=2048,
        description="URL do vídeo (somente sites permitidos)",
    )

    media_type: Literal["video", "audio"] = Field(
        default="video",
        description="video ou audio",
    )

    quality: Literal["360", "480", "720", "1080", "best"] = Field(
        default="best",
        description="360, 480, 720, 1080 ou best (teto de 1080p)",
    )
