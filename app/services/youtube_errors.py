class YoutubeAccessBlocked(RuntimeError):
    """YouTube refused an unauthenticated request from the worker host."""


def is_youtube_access_blocked(error: Exception) -> bool:
    message = str(error).lower()
    return any(phrase in message for phrase in (
        "sign in to confirm you’re not a bot",
        "sign in to confirm you're not a bot",
        "sign in to confirm your age",
        "this video may be inappropriate for some users",
    ))
