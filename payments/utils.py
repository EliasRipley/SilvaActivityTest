import re


def normalize_name(raw: str) -> str:
    """Normalize a name: strip whitespace, title-case, collapse multiple spaces."""
    if not raw:
        return ""
    cleaned = re.sub(r"\s+", " ", raw.strip())
    return cleaned.title()
