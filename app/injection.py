import re
from dataclasses import dataclass
from typing import List

FLAGS = re.IGNORECASE | re.DOTALL

INJECTION_PATTERNS = {
    "IGNORE_INSTRUCTIONS": re.compile(
        r"\b(?:ignore|disregard|forget)\b.{0,30}\b(?:previous|prior|above|earlier|all)\b.{0,30}\b(?:instructions|rules|prompts?|directions)\b",
        FLAGS,
    ),
    "REVEAL_SYSTEM_PROMPT": re.compile(
        r"\b(?:reveal|show|print|repeat|tell me)\b.{0,30}\b(?:system prompt|hidden instructions|initial instructions)\b",
        FLAGS,
    ),
    "ROLE_OVERRIDE": re.compile(
        r"\b(?:you are now|act as|pretend to be|pretend you are)\b.{0,40}\b(?:DAN|unfiltered|uncensored|jailbroken|without restrictions)\b",
        FLAGS,
    ),
    "DEVELOPER_MODE": re.compile(r"\b(?:developer|god|admin) mode\b", FLAGS),
}

@dataclass
class InjectionMatch:
    rule: str
    value: str
    start: int
    end: int

def find_injection(text: str) -> List[InjectionMatch]:
    matches = []
    for rule, pattern in INJECTION_PATTERNS.items():
        for m in pattern.finditer(text):
            matches.append(InjectionMatch(rule=rule, value=m.group(), start=m.start(), end=m.end()))
    return sorted(matches, key=lambda match: match.start)