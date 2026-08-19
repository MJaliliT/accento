import re
from urllib.parse import parse_qs, urlparse


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


class InvalidYouTubeUrl(ValueError):
    pass


def normalize_youtube_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS:
        raise InvalidYouTubeUrl("Enter a valid public YouTube video URL.")

    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    else:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
            video_id = parts[1]

    if not video_id or not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise InvalidYouTubeUrl("Enter a direct YouTube video URL, not a playlist.")

    return f"https://www.youtube.com/watch?v={video_id}"
