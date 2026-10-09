from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import app
from config import DOWNLOAD_DIR, MEDIA_API_KEY
from database.database import (
    create_download,
    delete_download,
    get_download,
)


HEADERS = {
    "X-API-Key": MEDIA_API_KEY,
}


def test_list_downloads():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/downloads",
            headers=HEADERS,
        )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_download_not_found():
    download_id = "download-inexistente-000"

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/downloads/{download_id}",
            headers=HEADERS,
        )

    assert response.status_code == 404


def test_download_progress_not_found():
    download_id = "download-inexistente-000"

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/downloads/{download_id}/progress",
            headers=HEADERS,
        )

    assert response.status_code == 404


def test_cannot_delete_active_download():
    download_id = "teste-seguranca-delete-001"

    with TestClient(app) as client:
        create_download(
            download_id,
            url="https://www.youtube.com/watch?v=teste",
            title="Download de teste",
            media_type="video",
            quality="360",
            status="downloading",
            progress=45.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            registro = get_download(download_id)

            assert registro is not None
            assert registro["status"] == "downloading"

            response = client.delete(
                f"/api/v1/downloads/{download_id}",
                headers=HEADERS,
            )

            assert response.status_code == 409

            data = response.json()
            assert "não é possível excluir" in data["detail"].lower()

            registro = get_download(download_id)

            assert registro is not None
            assert registro["status"] == "downloading"

        finally:
            delete_download(download_id)


def test_delete_download_not_found():
    download_id = "download-inexistente-delete-000"

    with TestClient(app) as client:
        response = client.delete(
            f"/api/v1/downloads/{download_id}",
            headers=HEADERS,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Download não encontrado."


def test_delete_download_rejects_filepath_outside_download_dir():
    download_id = "teste-caminho-fora-downloads-001"

    with TestClient(app) as client:
        create_download(
            download_id,
            url="https://www.youtube.com/watch?v=teste",
            title="Teste de segurança",
            media_type="video",
            quality="360",
            status="completed",
            progress=100.0,
            filepath=str(
                DOWNLOAD_DIR.parent / "arquivo_teste_nao_criar.txt"
            ),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            response = client.delete(
                f"/api/v1/downloads/{download_id}",
                headers=HEADERS,
            )

            assert response.status_code == 400

            assert response.json()["detail"] == (
                "Caminho de arquivo fora da pasta de downloads."
            )

            registro = get_download(download_id)
            assert registro is not None

        finally:
            delete_download(download_id)