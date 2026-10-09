from urllib.parse import urlsplit

from config import ALLOWED_SITES


class MediaError(Exception):
    """
    Erro com mensagem segura para ser exibida ao usuário.
    """


def get_allowed_domains() -> list[str]:
    return sorted(ALLOWED_SITES.keys())


def get_allowed_extractors() -> list[str]:
    """
    Lista de extratores do yt-dlp liberados, no formato
    esperado pela opção "allowed_extractors" (regex exata).
    """

    extractors = []

    for names in ALLOWED_SITES.values():
        for name in names:
            extractors.append(f"{name}$")

    return extractors


def validate_media_url(url: str) -> str:
    """
    Valida a URL antes de entregá-la ao yt-dlp.

    Aceita somente HTTPS, sem usuário/senha, sem porta
    e com domínio presente na lista de sites permitidos.
    """

    url = url.strip()

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise MediaError("Link inválido.")

    if parts.scheme != "https":
        raise MediaError("O link precisa começar com https://.")

    if parts.username or parts.password or port is not None:
        raise MediaError("Link inválido.")

    host = (parts.hostname or "").lower().rstrip(".")

    for domain in ALLOWED_SITES:
        if host == domain or host.endswith(f".{domain}"):
            return url

    raise MediaError(
        "Site não suportado. Sites aceitos: "
        + ", ".join(get_allowed_domains())
        + "."
    )
