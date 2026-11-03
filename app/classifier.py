import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

try:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

MODEL_NAME = os.getenv("GUARDRAILS_CLASSIFIER_MODEL", "protectai/deberta-v3-base-prompt-injection-v2")
THRESHOLD = float(os.getenv("GUARDRAILS_CLASSIFIER_THRESHOLD", "0.8"))


@dataclass
class ClassifierResult:
    model: str
    score: float
    is_injection: bool


def _pick_device() -> str:
    override = os.getenv("GUARDRAILS_DEVICE")
    if override:
        return override
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def _load_model():
    device = _pick_device()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).to(device)
    model.eval()
    return tokenizer, model, device


def classify_injection(text: str) -> Optional[ClassifierResult]:
    if not ML_AVAILABLE:
        return None
    tokenizer, model, device = _load_model()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    probabilities = torch.softmax(logits, dim=-1)[0]
    score = 1.0 - probabilities[0].item()
    return ClassifierResult(model=MODEL_NAME, score=score, is_injection=score >= THRESHOLD)