"""Robust JSON extraction from Claude responses (handles markdown fences)."""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array found in ``text``.

    Tolerates markdown code fences and surrounding prose. Raises ValueError if
    no parseable JSON is present.
    """
    if not text:
        raise ValueError("empty response")

    candidates: list[str] = []
    fenced = _FENCE.findall(text)
    candidates.extend(fenced)
    candidates.append(text)

    # also try the substring spanning the outermost braces/brackets
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start : end + 1])

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("no parseable JSON found in response")
