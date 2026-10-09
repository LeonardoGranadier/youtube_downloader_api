import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from config import MEDIA_API_KEY


api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


async def require_api_key(
    api_key: str | None = Security(api_key_header),
) -> None:
    """
    Valida a chave de acesso enviada no cabeçalho X-API-Key.
    """

    # Impede o acesso caso a chave não esteja configurada.
    if not MEDIA_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação da API não configurada.",
        )

    # Rejeita chaves ausentes ou inválidas.
    if not api_key or not secrets.compare_digest(
        api_key,
        MEDIA_API_KEY,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API ausente ou inválida.",
            headers={"WWW-Authenticate": "ApiKey"},
        )