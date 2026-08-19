import os
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from app.core.config import settings


ALLOWED_UPLOAD_TYPES = {
    "application/octet-stream",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
}


class UnsupportedMedia(RuntimeError):
    """The uploaded file is not readable media with an audio stream."""


class UploadMissing(RuntimeError):
    """The staged upload disappeared before the worker could process it."""


def ensure_upload_dir() -> Path:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return upload_dir


def upload_path_for(analysis_id: str, *, partial: bool = False) -> Path:
    if len(analysis_id) != 32 or any(char not in "0123456789abcdef" for char in analysis_id):
        raise ValueError("Invalid analysis ID")
    suffix = ".part" if partial else ".upload"
    return ensure_upload_dir() / f"{analysis_id}{suffix}"


def delete_upload(analysis_id: str) -> None:
    for partial in (False, True):
        try:
            upload_path_for(analysis_id, partial=partial).unlink(missing_ok=True)
        except OSError:
            pass


def cleanup_stale_uploads(max_age_seconds: int | None = None) -> int:
    cutoff = time.time() - (max_age_seconds or settings.UPLOAD_RETENTION_SECONDS)
    removed = 0

    with os.scandir(ensure_upload_dir()) as entries:
        for entry in entries:
            try:
                metadata = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_mtime >= cutoff:
                    continue
                os.unlink(entry.path)
                removed += 1
            except FileNotFoundError:
                continue
    return removed


def extract_audio_sample(analysis_id: str, seconds: int = 5) -> str:
    source = upload_path_for(analysis_id)
    if not source.is_file():
        raise UploadMissing("The staged upload is no longer available.")

    work_dir = tempfile.mkdtemp(prefix="accento-media-")
    output = os.path.join(work_dir, "sample.wav")
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-probesize", "5000000",
                "-analyzeduration", "5000000",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(source),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
        )
        if probe.returncode != 0 or "audio" not in probe.stdout.splitlines():
            raise UnsupportedMedia("The uploaded video has no readable audio stream.")

        conversion = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(source),
                "-map", "0:a:0",
                "-t", str(seconds),
                "-vn",
                "-sn",
                "-dn",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                output,
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
        if conversion.returncode != 0 or not os.path.isfile(output):
            raise UnsupportedMedia("FFmpeg could not decode the uploaded video.")
        return output
    except (subprocess.TimeoutExpired, OSError) as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise UnsupportedMedia("The uploaded video could not be decoded safely.") from exc
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
