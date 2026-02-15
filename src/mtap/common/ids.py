from __future__ import annotations

import random
import string


def make_sn(prefix: str = "SN", n: int = 4) -> str:
    return f"{prefix}{''.join(random.choices(string.digits, k=n))}"
