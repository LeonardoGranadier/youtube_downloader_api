from urllib.parse import urlsplit

from services.net_guard import is_public_ip, resolves_to_public_only


class MediaError(Exception):
    """
    Erro com mensagem segura para ser exibida ao usuário.
    """


def validate_media_url(url: str) -> str:
    """
    Validação antecipada, para responder 400 com mensagem clara antes de
    chamar o yt-dlp. Qualquer site é aceito (ADR-071 do Mil1), desde que
    seja http/https, sem usuário/senha, na porta padrão e apontando para
    um endereço público.

    A proteção de verdade contra SSRF (redirecionamentos, DNS rebinding,
    fragmentos de CDN) fica no net_guard, no nível do socket.
    """

    url = url.strip()

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise MediaError("Link inválido.")

    if parts.scheme not in ("http", "https"):
        raise MediaError("O link precisa começar com https:// ou http://.")

    if parts.username or parts.password:
        raise MediaError("Link inválido.")

    if port not in (None, 80, 443):
        raise MediaError("Link inválido: porta não permitida.")

    host = (parts.hostname or "").rstrip(".")

    if not host:
        raise MediaError("Link inválido.")

    # IP escrito direto no link: checado sem DNS.
    if host.replace(".", "").isdigit() or ":" in host:
        if not is_public_ip(host):
            raise MediaError("Esse endereço aponta para uma rede interna e não é permitido.")

        return url

    if not resolves_to_public_only(host):
        raise MediaError(
            "Não foi possível acessar esse endereço (site inexistente "
            "ou rede interna)."
        )

    return url
