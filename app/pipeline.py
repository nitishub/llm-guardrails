from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from app.classifier import ClassifierResult, classify_injection
from app.injection import InjectionMatch, find_injection
from app.normalize import normalize_text
from app.pii import PIIMatch, find_pii, redact_pii


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


def screen_prompt(text: str) -> Decision:
    normalized = normalize_text(text)

    injections = find_injection(normalized)
    classifier = None if injections else classify_injection(normalized)
    pii = find_pii(normalized)

    reasons = [f"injection rule: {m.rule}" for m in injections]
    if classifier is not None and classifier.is_injection:
        reasons.append(f"injection classifier score: {classifier.score:.2f}")

    if reasons:
        action, forwarded = Action.BLOCK, ""
    elif pii:
        action, forwarded = Action.REDACT, redact_pii(normalized, pii)
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
    )