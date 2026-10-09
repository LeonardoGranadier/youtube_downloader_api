"""
Proteção contra SSRF no nível do socket (ADR-071 do Mil1).

Com qualquer site liberado, o yt-dlp segue redirecionamentos, baixa
fragmentos de vídeo de CDNs e resolve nomes por conta própria. Validar só
a URL inicial não basta: um site pode redirecionar para um IP interno, ou
mudar o DNS entre a validação e a conexão (DNS rebinding).

Por isso toda resolução de nome do processo passa por aqui e só devolve
endereços públicos da internet. Como a conexão usa exatamente o endereço
devolvido por esta função, não existe janela entre checar e conectar.
"""

import ipaddress
import socket


_original_getaddrinfo = socket.getaddrinfo
_installed = False


def is_public_ip(address: str) -> bool:
    """
    True só para endereços roteáveis na internet pública. Recusa
    loopback, redes privadas (inclusive a fd12::/16 do Railway),
    link-local (169.254.169.254, metadados de nuvem), CGNAT, multicast,
    reservados e IPv4 embutido em IPv6 que aponte para algo disso.
    """

    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False

    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped or ip.sixtofour or (ip.teredo[1] if ip.teredo else None)

        if mapped is not None:
            return is_public_ip(str(mapped))

    return ip.is_global and not ip.is_multicast


def _is_bind_lookup(host, args, kwargs) -> bool:
    """
    Resolução feita pelo próprio servidor para abrir a porta (uvicorn
    com host "" vira getaddrinfo(None, porta, flags=AI_PASSIVE)). Não é
    conexão de saída.

    "0.0.0.0" e "::" NÃO entram aqui: como destino de conexão, no Linux
    eles levam à própria máquina.
    """

    flags = kwargs.get("flags", args[4] if len(args) > 4 else 0)

    return host in (None, "") or bool(flags & socket.AI_PASSIVE)


def _guarded_getaddrinfo(host, *args, **kwargs):
    results = _original_getaddrinfo(host, *args, **kwargs)

    if _is_bind_lookup(host, args, kwargs):
        return results

    allowed = [
        result
        for result in results
        if result[0] in (socket.AF_INET, socket.AF_INET6)
        and is_public_ip(result[4][0])
    ]

    if not allowed:
        raise socket.gaierror(
            socket.EAI_NONAME,
            f"Endereço bloqueado (não é público): {host}",
        )

    return allowed


def install() -> None:
    """
    Ativa a proteção para o processo inteiro. Idempotente.
    """

    global _installed

    if _installed:
        return

    socket.getaddrinfo = _guarded_getaddrinfo
    _installed = True


def resolves_to_public_only(host: str) -> bool:
    """
    Checagem antecipada (para devolver 400 com mensagem clara antes de
    chamar o yt-dlp). A proteção de verdade é o install().
    """

    try:
        results = _original_getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False

    addresses = [result[4][0] for result in results]

    return bool(addresses) and all(is_public_ip(address) for address in addresses)
