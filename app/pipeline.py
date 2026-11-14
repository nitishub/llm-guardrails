import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from app.classifier import THRESHOLD, ClassifierResult, classify_injection
from app.injection import InjectionMatch, find_injection
from app.judge import JudgeResult, judge_prompt
from app.normalize import normalize_text
from app.pii import PIIMatch, find_pii, redact_pii

GRAY_ZONE_LOW = float(os.getenv("GUARDRAILS_JUDGE_LOW", "0.5"))


class Action(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass
class Decision:
    action: Action
    text: str
    reasons: List[str]
    pii: List[PIIMatch]
    injections: List[InjectionMatch]
    classifier: Optional[ClassifierResult]
    judge: Optional[JudgeResult]


def screen_prompt(text: str) -> Decision:
    normalized = normalize_text(text)

    injections = find_injection(normalized)
    classifier = None if injections else classify_injection(normalized)
    pii = find_pii(normalized)
    redacted = redact_pii(normalized, pii) if pii else normalized

    judge = None
    if classifier is not None and not classifier.is_injection and classifier.score >= GRAY_ZONE_LOW:
        judge = judge_prompt(redacted)

    reasons = [f"injection rule: {m.rule}" for m in injections]
    if classifier is not None and classifier.is_injection:
        reasons.append(f"injection classifier score: {classifier.score:.2f}")
    if judge is not None and judge.is_injection:
        reasons.append(f"injection judge: {judge.reason}")

    if reasons:
        action, forwarded = Action.BLOCK, ""
    elif pii:
        action, forwarded = Action.REDACT, redacted
        reasons = [f"pii: {kind}" for kind in sorted({m.kind for m in pii})]
    else:
        action, forwarded = Action.ALLOW, normalized

    return Decision(
        action=action,
        text=forwarded,
        reasons=reasons,
        pii=pii,
        injections=injections,
        classifier=classifier,
        judge=judge,
    )