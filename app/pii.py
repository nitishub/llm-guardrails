import re
from dataclasses import dataclass
from typing import List

PII_PATTERNS = {
    "EMAIL": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "PHONE": re.compile(r"(?<!\d)(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
    "CREDIT_CARD": re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
}

@dataclass
class PIIMatch:
    kind: str
    value: str
    start: int
    end: int

def find_pii(text: str) -> List[PIIMatch]:
    matches = []
    for kind, pattern in PII_PATTERNS.items():
        for m in pattern.finditer(text):
            matches.append(PIIMatch(kind=kind, value=m.group(), start=m.start(), end=m.end()))
    return sorted(matches, key=lambda match: match.start)

def redact_pii(text: str, matches: List[PIIMatch]) -> str:
    parts = []
    cursor = 0
    for match in matches:
        if match.end <= cursor:        # fully inside an earlier match
            continue
        start = max(match.start, cursor)
        parts.append(text[cursor:start])
        parts.append(f"[{match.kind}]")
        cursor = match.end
    parts.append(text[cursor:])
    return "".join(parts)