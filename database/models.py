from dataclasses import dataclass
from typing import Optional


@dataclass
class Download:
    id: str
    url: str

    title: Optional[str] = None
    uploader: Optional[str] = None
    thumbnail: Optional[str] = None

    media_type: str = "video"
    quality: Optional[str] = None

    status: str = "queued"

    progress: float = 0.0

    speed: Optional[str] = None
    eta: Optional[str] = None

    filename: Optional[str] = None
    filepath: Optional[str] = None

    error: Optional[str] = None

    created_at: Optional[str] = None
    completed_at: Optional[str] = None