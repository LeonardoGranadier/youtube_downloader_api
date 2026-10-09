from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from api.files import get_safe_file_path


def test_file_traversal_path_is_rejected():
    try:
        get_safe_file_path("../app.py")
        assert False, "O caminho inválido deveria ser rejeitado."
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Caminho de arquivo inválido."


def test_file_traversal_get_is_rejected():
    with TestClient(app) as client:
        response = client.get("/api/v1/files/%2E%2E%2Fapp.py")

    assert response.status_code in (400, 404)


def test_file_traversal_delete_is_rejected():
    with TestClient(app) as client:
        response = client.delete("/api/v1/files/%2E%2E%2Fapp.py")

    assert response.status_code in (400, 404)