import re
import unicodedata

INVISIBLE_CHARS = re.compile(r"[\u00ad\u200b-\u200d\u2060\ufeff\U000e0000-\U000e007f]")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return INVISIBLE_CHARS.sub("", text)