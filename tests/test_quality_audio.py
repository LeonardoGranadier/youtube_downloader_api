import subprocess

import pytest
from fastapi.testclient import TestClient

from app import app
from config import FFMPEG_PATH, MEDIA_API_KEY
from services.downloader import _safe_thumbnail, pick_audio_donor, pick_video_format
from services.ffmpeg import has_audio_stream, merge_video_audio, video_codec
from services.url_policy import MediaError


HEADERS = {
    "X-API-Key": MEDIA_API_KEY,
}

# Formatos reais do Wikimedia Commons (Big_Buck_Bunny_4K.webm, 2026-10-09):
# o 360p é o único sem áudio.
WIKIMEDIA_FORMATS = [
    {"format_id": "0", "height": 240, "vcodec": "vp9", "acodec": "opus", "filesize_approx": 30_000_000},
    {"format_id": "1", "height": 360, "vcodec": "mp4v", "acodec": "none", "filesize_approx": 130_000_000},
    {"format_id": "2", "height": 480, "vcodec": "vp9", "acodec": "opus", "filesize_approx": 96_000_000},
    {"format_id": "3", "height": 1080, "vcodec": "vp9", "acodec": "opus", "filesize_approx": 300_000_000},
    {"format_id": "4", "height": 2250, "vcodec": "vp8", "acodec": "vorbis", "filesize_approx": 2_900_000_000},
]

# archive.org informa codecs desconhecidos (sem "acodec"/"vcodec" úteis).
ARCHIVE_FORMATS = [
    {"format_id": "0", "height": 300, "ext": "ogv", "filesize": 46_000_000},
    {"format_id": "1", "height": 360, "ext": "mp4", "filesize": 61_000_000},
    {"format_id": "2", "height": 720, "ext": "avi", "filesize": 332_000_000},
]


def test_exact_quality_is_respected_even_without_audio():
    assert pick_video_format(WIKIMEDIA_FORMATS, "360")["format_id"] == "1"


def test_best_is_capped_at_1080():
    assert pick_video_format(WIKIMEDIA_FORMATS, "best")["format_id"] == "3"


def test_unavailable_quality_is_rejected():
    with pytest.raises(MediaError, match="720p não disponível"):
        pick_video_format(WIKIMEDIA_FORMATS, "720")


def test_quality_above_1080_is_never_picked():
    with pytest.raises(MediaError):
        pick_video_format(WIKIMEDIA_FORMATS, "2250")


def test_unknown_codecs_count_as_video():
    assert pick_video_format(ARCHIVE_FORMATS, "720")["format_id"] == "2"


def test_audio_donor_is_the_lightest_version_with_audio():
    donor = pick_audio_donor(WIKIMEDIA_FORMATS, exclude_id="1")

    assert donor is not None
    assert donor["format_id"] == "0"


def test_audio_donor_prefers_an_audio_only_track():
    formats = WIKIMEDIA_FORMATS + [
        {"format_id": "a", "vcodec": "none", "acodec": "opus", "filesize_approx": 9_000_000},
    ]

    assert pick_audio_donor(formats, exclude_id="1")["format_id"] == "a"


def test_audio_donor_with_unknown_codecs_falls_back_to_other_versions():
    donor = pick_audio_donor(ARCHIVE_FORMATS, exclude_id="2")

    assert donor is not None
    assert donor["format_id"] != "2"


def test_no_audio_donor_when_nothing_else_exists():
    only_video = [{"format_id": "1", "height": 360, "vcodec": "h264", "acodec": "none"}]

    assert pick_audio_donor(only_video, exclude_id="1") is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://upload.wikimedia.org/thumb.jpg", "https://upload.wikimedia.org/thumb.jpg"),
        ("https://archive.org/download/x/thumb.jpg", "https://archive.org/download/x/thumb.jpg"),
        ("https://tracker.example.com/pixel.gif", None),
        ("http://archive.org/thumb.jpg", None),
        (None, None),
    ],
)
def test_thumbnail_only_from_allowed_sites_over_https(url, expected):
    assert _safe_thumbnail(url) == expected


@pytest.mark.parametrize("quality", ["2160", "abc", "0", "36", "1080p"])
def test_download_rejects_invalid_quality_before_calling_the_site(quality):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/media/download",
            json={"url": "https://archive.org/details/x", "quality": quality},
            headers=HEADERS,
        )

    assert response.status_code == 422


def _make_media(path, args):
    subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", *args, str(path)],
        check=True,
        timeout=60,
    )


def test_merge_adds_audio_to_a_silent_video(tmp_path):
    # Arquivos reais: vídeo h264 mudo + áudio opus separado.
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.webm"

    _make_media(video, ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=24:duration=2", "-c:v", "libx264", "-an"])
    _make_media(audio, ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "libopus"])

    assert not has_audio_stream(video)

    result = merge_video_audio(video, audio, tmp_path / "final")

    assert result.suffix == ".mp4"
    assert has_audio_stream(result)
    assert video_codec(result) == "h264"


def test_merge_uses_mkv_for_codecs_mp4_does_not_take(tmp_path):
    video = tmp_path / "video.webm"
    audio = tmp_path / "audio.ogg"

    _make_media(video, ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=2", "-c:v", "libvpx", "-an"])
    _make_media(audio, ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "libvorbis"])

    result = merge_video_audio(video, audio, tmp_path / "final")

    assert result.suffix == ".mkv"
    assert has_audio_stream(result)
    assert video_codec(result) == "vp8"
