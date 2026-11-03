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
        r"\b(?:reveal|show|print|repeat|tell\s+me)\b.{0,30}\b(?:system\s+prompt|hidden\s+instructions|initial\s+instructions)\b",
        FLAGS,
    ),
    "ROLE_OVERRIDE": re.compile(
        r"\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be|pretend\s+you\s+are)\b.{0,40}\b(?:DAN|unfiltered|uncensored|jailbroken|without\s+restrictions)\b",
        FLAGS,
    ),
    "DEVELOPER_MODE": re.compile(r"\b(?:developer|god|admin)\s+mode\b", FLAGS),
    "FAKE_ROLE_TAG": re.compile(
        r"<\|[a-z_]+\|>"  # chat-template special tokens (OpenAI ChatML, Llama 3): <|im_start|>, <|eot_id|>
        r"|</?\s*(?:system|assistant|developer)\s*>"  # XML-style role tags (Policy Puppetry): <system>, </system>
        r"|\[/?\s*(?:system|inst)\s*\]"  # Llama 2 / Mistral instruction format: [INST], [/INST], [SYSTEM]
        r"|<<\s*/?\s*sys\s*>>"  # Llama 2 system-prompt markers: <<SYS>>, <</SYS>>
        r"|<!--\s*(?:system|assistant|developer)\b",  # hidden HTML comments (indirect injection): <!-- SYSTEM:
        FLAGS,
    ),
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