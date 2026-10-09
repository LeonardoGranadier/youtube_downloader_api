from typing import Literal

from pydantic import BaseModel, Field, field_validator


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

    # Altura exata em pixels (uma das "available_heights" de /media/info)
    # ou "best" (a maior até 1080p). O teto é conferido no downloader.
    quality: str = Field(
        default="best",
        pattern=r"^(best|[1-9][0-9]{2,3})$",
        description="best ou a altura exata, ex.: 360, 720, 1080",
    )

    @field_validator("quality")
    @classmethod
    def quality_up_to_1080(cls, value: str) -> str:
        # Recusado já na entrada (422), sem consultar o site.
        if value != "best" and int(value) > 1080:
            raise ValueError("Qualidade máxima: 1080p.")

        return value
