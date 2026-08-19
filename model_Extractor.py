import os
from pathlib import Path

import torch
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification

MODEL_NAME = "MilesPurvis/english-accent-classifier"

model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_NAME)
model.eval()
output_dir = Path(os.getenv("MODEL_OUTPUT_DIR", "app/services/accent_model"))
output_dir.mkdir(parents=True, exist_ok=True)

# dummy 5-second audio input (16kHz)
dummy_input = torch.randn(1, 16000 * 5)

torch.onnx.export(
    model,
    (dummy_input,),
    output_dir / "accent_model.onnx",
    input_names=["input_values"],
    output_names=["logits"],
    dynamic_axes={
        "input_values": {1: "audio_length"},
        "logits": {0: "batch_size"}
    },
    opset_version=18,
    dynamo=False,
)

model.config.save_pretrained(output_dir)
Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME).save_pretrained(output_dir)

print("Exported accent_model.onnx")
