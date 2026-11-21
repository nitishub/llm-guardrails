import os

os.environ["OPENAI_API_KEY"] = "sk-test-not-a-real-key"
os.environ["GUARDRAILS_API_KEY"] = "test-api-key"

import pytest

from app import main, pipeline
from tests.helpers import fake_classifier, unexpected_call


@pytest.fixture(autouse=True)
def offline_layers(monkeypatch):
    monkeypatch.setattr(pipeline, "classify_injection", fake_classifier(0.0))
    monkeypatch.setattr(pipeline, "judge_prompt", unexpected_call)
    monkeypatch.setattr(main, "call_llm", lambda prompt: f"fake answer to: {prompt}")