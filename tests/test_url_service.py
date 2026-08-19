import pytest

from app.services.url_service import InvalidYouTubeUrl, normalize_youtube_url


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=ignored",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        (
            "https://youtu.be/dQw4w9WgXcQ?t=42",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        (
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
    ],
)
def test_normalizes_supported_youtube_urls(source, expected):
    assert normalize_youtube_url(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ",
        "file:///etc/passwd",
        "https://www.youtube.com/playlist?list=PL123456",
        "https://www.youtube.com/watch?v=bad!id",
    ],
)
def test_rejects_non_video_or_untrusted_urls(source):
    with pytest.raises(InvalidYouTubeUrl):
        normalize_youtube_url(source)
