import re
from typing import Optional, Tuple


def normalize_inn(inn: Optional[str]) -> Tuple[Optional[str], bool]:
    """Return (normalized_inn, is_invalid)."""
    if not inn:
        return None, True
    digits = re.sub(r"\D", "", inn)
    if len(digits) in (10, 12):
        return digits, False
    return digits or None, True
