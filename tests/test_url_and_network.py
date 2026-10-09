import socket

import pytest

from services import net_guard
from services.downloader import _check_single_video, _safe_formats, pick_audio_source, pick_video_format
from services.url_policy import MediaError, validate_media_url


# DNS falso: nome -> IPs. Testes não dependem da internet e simulam
# ataques (nome público apontando para IP interno etc.).
FAKE_DNS = {
    "videos.example.com": ["93.184.216.34"],
    "cdn.example.com": ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"],
    "rebind.example.com": ["127.0.0.1"],
    "metadata.example.com": ["169.254.169.254"],
    "mixed.example.com": ["93.184.216.34", "10.0.0.5"],
    "railway-internal.example.com": ["fd12:3456::1"],
    "mapped.example.com": ["::ffff:127.0.0.1"],
    "cgnat.example.com": ["100.64.0.1"],
}


def _fake_getaddrinfo(host, port=None, *args, **kwargs):
    if host in (None, ""):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("0.0.0.0", port or 0))]

    try:
        socket.inet_pton(socket.AF_INET, host)
        addresses = [host]
    except OSError:
        try:
            socket.inet_pton(socket.AF_INET6, host)
            addresses = [host]
        except OSError:
            if host not in FAKE_DNS:
                raise socket.gaierror(socket.EAI_NONAME, "not found")
            addresses = FAKE_DNS[host]

    return [
        (
            socket.AF_INET6 if ":" in address else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (address, port or 0) if ":" not in address else (address, port or 0, 0, 0),
        )
        for address in addresses
    ]


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    monkeypatch.setattr(net_guard, "_original_getaddrinfo", _fake_getaddrinfo)


@pytest.mark.parametrize(
    "address",
    ["93.184.216.34", "1.1.1.1", "2606:2800:220:1:248:1893:25c8:1946"],
)
def test_public_ips(address):
    assert net_guard.is_public_ip(address)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254",
        "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "::", "fd12:3456::1", "fe80::1",
        "::ffff:127.0.0.1", "::ffff:10.0.0.1", "2002:7f00:0001::1", "not-an-ip",
    ],
)
def test_non_public_ips(address):
    assert not net_guard.is_public_ip(address)


@pytest.mark.parametrize(
    "url",
    [
        "https://videos.example.com/watch/123",
        "http://videos.example.com/video.mp4",
        "https://cdn.example.com:443/a.webm",
        "https://93.184.216.34/video.mp4",
    ],
)
def test_any_public_site_is_accepted(url):
    assert validate_media_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://rebind.example.com/x",
        "https://metadata.example.com/latest/meta-data",
        "https://mixed.example.com/x",
        "https://railway-internal.example.com/x",
        "https://mapped.example.com/x",
        "https://cgnat.example.com/x",
        "http://127.0.0.1/x",
        "http://0.0.0.0:80/x",
        "http://[::1]/x",
        "http://2130706433/x",
        "https://nao-existe.example.com/x",
        "https://user:pass@videos.example.com/x",
        "https://videos.example.com:8080/x",
        "file:///etc/passwd",
        "ftp://videos.example.com/x",
        "gopher://videos.example.com/x",
        "https://[::1/",
    ],
)
def test_internal_or_invalid_urls_are_rejected(url):
    with pytest.raises(MediaError):
        validate_media_url(url)


def test_socket_guard_blocks_internal_resolution_at_connect_time():
    # O que o yt-dlp chama ao seguir um redirecionamento: precisa falhar.
    for host in ("rebind.example.com", "metadata.example.com", "127.0.0.1", "0.0.0.0", "::1"):
        with pytest.raises(socket.gaierror):
            net_guard._guarded_getaddrinfo(host, 443, 0, socket.SOCK_STREAM)


def test_socket_guard_drops_internal_addresses_from_mixed_answers():
    results = net_guard._guarded_getaddrinfo("mixed.example.com", 443)

    assert [r[4][0] for r in results] == ["93.184.216.34"]


def test_socket_guard_lets_the_server_bind_its_own_port():
    # uvicorn com host "" -> getaddrinfo(None, porta, flags=AI_PASSIVE).
    results = net_guard._guarded_getaddrinfo(None, 8000, 0, socket.SOCK_STREAM, 0, socket.AI_PASSIVE)

    assert results


def test_socket_guard_is_installed_process_wide():
    import app  # noqa: F401  (instala ao importar)

    assert socket.getaddrinfo is net_guard._guarded_getaddrinfo


def test_unsafe_protocols_are_never_selected():
    formats = [
        {"format_id": "rtmp", "height": 720, "protocol": "rtmp", "vcodec": "h264", "acodec": "aac"},
        {"format_id": "hls", "height": 480, "protocol": "m3u8_native", "vcodec": "h264", "acodec": "aac"},
        {"format_id": "file", "url": "file:///etc/passwd", "height": 360, "vcodec": "h264"},
    ]

    assert [f["format_id"] for f in _safe_formats(formats)] == ["hls"]
    assert pick_video_format(formats, "best")["format_id"] == "hls"
    with pytest.raises(MediaError):
        pick_video_format(formats, "720")


def test_direct_link_without_height_downloads_the_original():
    # Como o extrator genérico descreve um link direto .mp4.
    formats = [{"format_id": "mp4", "url": "https://videos.example.com/a.mp4", "ext": "mp4", "protocol": "https"}]

    assert pick_video_format(formats, "best")["format_id"] == "mp4"
    with pytest.raises(MediaError):
        pick_video_format(formats, "360")


def test_audio_source_prefers_audio_only_then_small_video():
    formats = [
        {"format_id": "v1080", "height": 1080, "vcodec": "vp9", "acodec": "opus", "filesize": 300, "protocol": "https"},
        {"format_id": "v240", "height": 240, "vcodec": "vp9", "acodec": "opus", "filesize": 30, "protocol": "https"},
    ]

    assert pick_audio_source(formats)["format_id"] == "v240"

    formats.append({"format_id": "a", "vcodec": "none", "acodec": "opus", "filesize": 9, "protocol": "https"})

    assert pick_audio_source(formats)["format_id"] == "a"


def test_audio_source_rejects_silent_links():
    with pytest.raises(MediaError, match="não tem áudio"):
        pick_audio_source([{"format_id": "v", "height": 360, "vcodec": "h264", "acodec": "none", "protocol": "https"}])


@pytest.mark.parametrize("info", [{"_type": "playlist", "entries": []}, {"_type": "multi_video"}, {"entries": [{}]}])
def test_pages_with_many_videos_ask_for_a_single_link(info):
    with pytest.raises(MediaError, match="vários vídeos"):
        _check_single_video(info)
