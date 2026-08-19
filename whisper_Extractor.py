import os
from pathlib import Path

from faster_whisper.utils import download_model


model_root = Path(os.getenv("MODEL_OUTPUT_DIR", "app/services/accent_model"))
output_dir = model_root / "whisper-tiny"
output_dir.mkdir(parents=True, exist_ok=True)
download_model("tiny", output_dir=str(output_dir))
print("Downloaded whisper-tiny")
