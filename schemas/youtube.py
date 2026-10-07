from pydantic import BaseModel, Field


class YouTubeInfoRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=5,
        description="URL do vídeo do YouTube",
    )


class YouTubeInfoResponse(BaseModel):
    id: str | None = None
    title: str | None = None
    uploader: str | None = None
    thumbnail: str | None = None
    duration: int | None = None
    webpage_url: str | None = None
    available_heights: list[int] = []


class YouTubeDownloadRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=5,
        description="URL do vídeo do YouTube",
    )

    media_type: str = Field(
        default="video",
        description="video ou audio",
    )

    quality: str = Field(
        default="best",
        description="360, 480, 720, 1080, 1440, 2160 ou best",
    )