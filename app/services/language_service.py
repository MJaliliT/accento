from faster_whisper import WhisperModel

from app.core.logger import logger

_LANG_MODEL = None
MODEL_DIR = "/app/app/services/accent_model/whisper-tiny"


def get_model():
    global _LANG_MODEL

    if _LANG_MODEL is None:
        logger.info("Loading whisper model")

        _LANG_MODEL = WhisperModel(
            MODEL_DIR,
            device="cpu",
            compute_type="int8",
            local_files_only=True,
        )

    return _LANG_MODEL


def detect_language(audio_path: str):
    model = get_model()

    _, info = model.transcribe(
        audio_path,
        beam_size=1
    )

    return info.language
