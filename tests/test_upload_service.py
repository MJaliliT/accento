import os
import time

import pytest

from app.core.config import settings
from app.services.upload_service import (
    cleanup_stale_uploads,
    upload_path_for,
)


def test_upload_path_uses_server_generated_id(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    analysis_id = "a" * 32

    assert upload_path_for(analysis_id) == tmp_path / f"{analysis_id}.upload"
    assert upload_path_for(analysis_id, partial=True) == tmp_path / f"{analysis_id}.part"


@pytest.mark.parametrize("analysis_id", ["../escape", "A" * 32, "a" * 31, "g" * 32])
def test_upload_path_rejects_untrusted_names(monkeypatch, tmp_path, analysis_id):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        upload_path_for(analysis_id)


def test_cleanup_removes_only_stale_regular_files(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    stale = tmp_path / f"{'a' * 32}.upload"
    fresh = tmp_path / f"{'b' * 32}.upload"
    stale.write_bytes(b"old")
    fresh.write_bytes(b"new")
    old_time = time.time() - 120
    os.utime(stale, (old_time, old_time))

    removed = cleanup_stale_uploads(max_age_seconds=60)

    assert removed == 1
    assert not stale.exists()
    assert fresh.read_bytes() == b"new"
