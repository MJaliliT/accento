import json

import numpy as np
import onnxruntime as ort
import soundfile as sf

from app.core.logger import logger

MODEL_DIR = "/app/app/services/accent_model"

_SESSION = None
_ID2LABEL = None


def get_model():
    global _SESSION, _ID2LABEL

    if _SESSION is None:
        available_providers = ort.get_available_providers()
        preferred_providers = [
            provider
            for provider in ("CUDAExecutionProvider", "CPUExecutionProvider")
            if provider in available_providers
        ]
        _SESSION = ort.InferenceSession(
            f"{MODEL_DIR}/accent_model.onnx",
            providers=preferred_providers,
        )

        with open(f"{MODEL_DIR}/config.json", encoding="utf-8") as config_file:
            labels = json.load(config_file)["id2label"]
        _ID2LABEL = {int(index): label for index, label in labels.items()}

    return _SESSION, _ID2LABEL


def detect_accent(audio_path: str):
    session, id2label = get_model()
    logger.info("Running accent model")

    audio, sample_rate = sf.read(audio_path, dtype="float32", always_2d=True)
    if sample_rate != 16000:
        raise ValueError(f"Expected 16 kHz audio, received {sample_rate} Hz")

    audio = audio.mean(axis=1)[: 5 * 16000]
    if audio.size == 0:
        raise ValueError("Audio sample is empty")

    variance = np.var(audio)
    audio = (audio - np.mean(audio)) / np.sqrt(variance + 1e-7)
    logits = session.run(
        None,
        {"input_values": audio[np.newaxis, :].astype("float32")},
    )[0][0]

    shifted = logits - np.max(logits)
    probabilities = np.exp(shifted) / np.exp(shifted).sum()
    results = {
        id2label[index]: float(probability)
        for index, probability in enumerate(probabilities)
    }
    top_accent = max(results, key=results.get)
    normalized_accent = top_accent.lower().replace(" ", "_")
    return normalized_accent, results[top_accent], results
