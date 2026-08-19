from app.services.youtube_errors import is_youtube_access_blocked


def test_detects_youtube_bot_block_message():
    error = RuntimeError("Sign in to confirm you’re not a bot. Use --cookies")
    assert is_youtube_access_blocked(error)


def test_does_not_misclassify_generic_download_failure():
    error = RuntimeError("HTTP Error 503: Service Unavailable")
    assert not is_youtube_access_blocked(error)
