from pydantic import BaseModel


class DownloadResponse(BaseModel):
    id: str
    url: str

    title: str | None = None
    uploader: str | None = None
    thumbnail: str | None = None

    media_type: str
    quality: str | None = None

    status: str
    progress: float = 0

    speed: str | None = None
    eta: str | None = None

    filename: str | None = None
    filepath: str | None = None

    error: str | None = None

    created_at: str | None = None
    completed_at: str | None = None