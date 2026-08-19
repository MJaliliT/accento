import glob
import os
import shutil
import tempfile

import yt_dlp
from yt_dlp.utils import DownloadError, download_range_func

from app.core.config import settings
from app.core.logger import logger
from app.services.youtube_errors import YoutubeAccessBlocked, is_youtube_access_blocked


def youtube_options() -> dict:
    return {
        "js_runtimes": {"deno": {"path": None}},
        "extractor_args": {
            "youtube": {"player_client": ["mweb"]},
            "youtubepot-bgutilhttp": {
                "base_url": [settings.POT_PROVIDER_URL],
            },
        },
    }


def get_video_info(url: str):
    options = {
        **youtube_options(),
        "quiet": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 2,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        if is_youtube_access_blocked(exc):
            raise YoutubeAccessBlocked(
                "YouTube rejected the worker host before media extraction."
            ) from exc
        logger.exception("Video metadata extraction failed")
        raise

    return {
        "title": info.get("title"),
        "description": info.get("description"),
        "is_live": info.get("is_live"),
        "live_status": info.get("live_status")
    }


def download_audio(url: str, seconds: int = 5):
    work_dir = tempfile.mkdtemp(prefix="accento-", dir=None)
    output = os.path.join(work_dir, "sample.%(ext)s")
    opts = {
        **youtube_options(),
        "format": "bestaudio/best",
        "outtmpl": output,
        "download_ranges": download_range_func(None, [(0, seconds)]),
        "force_keyframes_at_cuts": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "postprocessor_args": ["-ar", "16000", "-ac", "1"],
        "noplaylist": True,
        "quiet": True,
        "socket_timeout": 15,
        "retries": 2,
        "fragment_retries": 2,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        matches = glob.glob(os.path.join(work_dir, "*.wav"))
        if not matches:
            raise RuntimeError("Audio conversion did not produce a WAV file")
        return matches[0]
    except DownloadError as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        if is_youtube_access_blocked(exc):
            raise YoutubeAccessBlocked(
                "YouTube rejected the worker host during media extraction."
            ) from exc
        logger.exception("Audio download failed")
        raise
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.exception("Audio conversion failed")
        raise
