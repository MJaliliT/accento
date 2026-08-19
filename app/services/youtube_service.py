import glob
import os
import tempfile

import yt_dlp
from yt_dlp.utils import download_range_func

from app.core.logger import logger


def get_video_info(url: str):
    with yt_dlp.YoutubeDL({
        "quiet": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 2,
    }) as ydl:
        info = ydl.extract_info(url, download=False)

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
    except Exception:
        logger.exception("Audio download failed")
        raise
