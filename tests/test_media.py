import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import app
from api.downloads import friendly_filename
from config import DOWNLOAD_DIR, MEDIA_API_KEY
from database.database import create_download, delete_download, get_download
from services.download_manager import cleanup_expired
from services.url_policy import (
    MediaError,
    get_allowed_extractors,
    validate_media_url,
)


HEADERS = {
    "X-API-Key": MEDIA_API_KEY,
}


@pytest.mark.parametrize(
    "url",
    [
        "https://archive.org/details/BigBuckBunny_124",
        "https://www.archive.org/details/BigBuckBunny_124",
        "https://commons.wikimedia.org/wiki/File:Big_Buck_Bunny_4K.webm",
    ],
)
def test_allowed_urls(url):
    assert validate_media_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
        "https://youtu.be/aqz-KE-bpKQ",
        "https://vimeo.com/76979871",
        "http://archive.org/details/x",
        "https://localhost/video.mp4",
        "https://169.254.169.254/latest/meta-data",
        "https://postgres.railway.internal/",
        "https://archive.org.evil.com/x",
        "https://evilarchive.org/x",
        "https://user:pass@archive.org/details/x",
        "https://archive.org:8080/details/x",
        "file:///etc/passwd",
        "ftp://archive.org/x",
        "https://[::1/",
    ],
)
def test_rejected_urls(url):
    with pytest.raises(MediaError):
        validate_media_url(url)


def test_generic_extractor_is_never_allowed():
    extractors = get_allowed_extractors()

    assert extractors
    assert not any("generic" in name for name in extractors)


def test_media_requires_api_key():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/media/info",
            json={"url": "https://archive.org/details/x"},
        )

    assert response.status_code == 401


def test_media_sites():
    with TestClient(app) as client:
        response = client.get("/api/v1/media/sites", headers=HEADERS)

    assert response.status_code == 200
    assert "archive.org" in response.json()["domains"]
    assert "youtube.com" not in response.json()["domains"]


def test_info_rejects_youtube_without_calling_ytdlp():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/media/info",
            json={"url": "https://www.youtube.com/watch?v=aqz-KE-bpKQ"},
            headers=HEADERS,
        )

    assert response.status_code == 400
    assert "Site não suportado" in response.json()["detail"]


def test_download_rejects_internal_host():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/media/download",
            json={"url": "https://postgres.railway.internal/"},
            headers=HEADERS,
        )

    assert response.status_code == 400


def test_download_rejects_quality_above_1080():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/media/download",
            json={
                "url": "https://archive.org/details/x",
                "quality": "2160",
            },
            headers=HEADERS,
        )

    assert response.status_code == 422


def test_friendly_filename():
    assert friendly_filename("Big Buck Bunny", ".mp4") == "Big Buck Bunny.mp4"
    assert friendly_filename("../../etc/passwd", ".mp4") == "etcpasswd.mp4"
    assert friendly_filename('a/b\\c:d*?"<>|', ".mp3") == "abcd.mp3"
    assert friendly_filename(None, ".mp4") == "video.mp4"


def test_file_endpoint_requires_completed_download():
    download_id = "teste-arquivo-nao-pronto-001"

    create_download(
        download_id,
        url="https://archive.org/details/x",
        media_type="video",
        status="downloading",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/downloads/{download_id}/file",
                headers=HEADERS,
            )

        assert response.status_code == 404

    finally:
        delete_download(download_id)


def test_cleanup_removes_only_expired_downloads():
    old = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    now = datetime.now(timezone.utc).isoformat()

    expired_file = DOWNLOAD_DIR / "teste-expirado-001.mp4"
    fresh_file = DOWNLOAD_DIR / "teste-recente-001.mp4"

    expired_file.write_bytes(b"x")
    fresh_file.write_bytes(b"x")

    create_download(
        "teste-expirado-001",
        url="https://archive.org/details/x",
        media_type="video",
        status="completed",
        filepath=str(expired_file),
        created_at=old,
        completed_at=old,
    )

    create_download(
        "teste-recente-001",
        url="https://archive.org/details/x",
        media_type="video",
        status="completed",
        filepath=str(fresh_file),
        created_at=now,
        completed_at=now,
    )

    # Download ativo antigo nunca deve ser apagado pela limpeza.
    create_download(
        "teste-ativo-antigo-001",
        url="https://archive.org/details/x",
        media_type="video",
        status="downloading",
        created_at=old,
    )

    try:
        cleanup_expired()

        assert get_download("teste-expirado-001") is None
        assert not expired_file.exists()

        assert get_download("teste-recente-001") is not None
        assert fresh_file.exists()

        assert get_download("teste-ativo-antigo-001") is not None

    finally:
        for download_id in (
            "teste-expirado-001",
            "teste-recente-001",
            "teste-ativo-antigo-001",
        ):
            delete_download(download_id)

        fresh_file.unlink(missing_ok=True)
        expired_file.unlink(missing_ok=True)


def test_cleanup_removes_old_orphan_files():
    orphan = DOWNLOAD_DIR / "teste-orfao-001.mp4.part"
    orphan.write_bytes(b"x")

    old = (datetime.now() - timedelta(days=1)).timestamp()
    os.utime(orphan, (old, old))

    try:
        cleanup_expired()

        assert not orphan.exists()

    finally:
        orphan.unlink(missing_ok=True)
