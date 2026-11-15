from app.classifier import ClassifierResult
from app.pipeline import THRESHOLD


def fake_classifier(score):
    def classify(text):
        return ClassifierResult(model="fake", score=score, is_injection=score >= THRESHOLD)

    return classify


def unexpected_call(*args, **kwargs):
    raise AssertionError("this layer should not have been called")