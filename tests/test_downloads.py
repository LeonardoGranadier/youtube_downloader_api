from fastapi.testclient import TestClient
from datetime import datetime, timezone

from database.database import create_download, delete_download, get_download

from pathlib import Path
from config import DOWNLOAD_DIR
from app import app


def test_list_downloads():
    with TestClient(app) as client:
        response = client.get("/api/v1/downloads")

    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_download_not_found():
    download_id = "download-inexistente-000"

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/downloads/{download_id}"
        )

    assert response.status_code == 404

def test_download_progress_not_found():
    download_id = "download-inexistente-000"

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/downloads/{download_id}/progress"
        )

    assert response.status_code == 404

def test_cannot_delete_active_download():
    download_id = "teste-seguranca-delete-001"

    with TestClient(app) as client:
        # Cria o registro depois que o lifespan foi executado.
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
            # Confirma que o registro continua ativo.
            registro = get_download(download_id)
            assert registro is not None
            assert registro["status"] == "downloading"

            # Tenta excluir pela API.
            response = client.delete(
                f"/api/v1/downloads/{download_id}"
            )

            # A exclusão deve ser bloqueada.
            assert response.status_code == 409

            data = response.json()
            assert "não é possível excluir" in data["detail"].lower()

            # Confirma que o registro continua no banco.
            registro = get_download(download_id)
            assert registro is not None
            assert registro["status"] == "downloading"

        finally:
            # Remove apenas o registro criado pelo teste.
            delete_download(download_id)

def test_delete_download_not_found():
    download_id = "download-inexistente-delete-000"

    with TestClient(app) as client:
        response = client.delete(
            f"/api/v1/downloads/{download_id}"
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
            filepath=str(DOWNLOAD_DIR.parent / "arquivo_teste_nao_criar.txt"),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            response = client.delete(
                f"/api/v1/downloads/{download_id}"
            )

            assert response.status_code == 400
            assert response.json()["detail"] == (
                "Caminho de arquivo fora da pasta de downloads."
            )

            # O registro deve continuar no banco.
            registro = get_download(download_id)
            assert registro is not None

        finally:
            delete_download(download_id)