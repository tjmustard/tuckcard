"""The approval hash one card's content is compared against.

SPEC.md section 6 says which fields the hash covers: the title, the lines
(text, mark and note), the category and the visibility. It does not cover the
card number, the rules cited or the approval record itself.

This module uses only the standard library, so ``lint.py`` can compare a card
without Pillow and ``render_core.py`` can list a hand edit without importing
lint. Both call the same functions, so the two cannot drift.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def card_content(card: Dict[str, Any]) -> Dict[str, Any]:
    """The covered fields of SPEC.md section 6's approval hash."""
    lines: List[Dict[str, Any]] = []
    raw_lines = card.get("lines")
    if isinstance(raw_lines, list):
        for line in raw_lines:
            if not isinstance(line, dict):
                continue
            mark = line.get("mark")
            mark_data = None
            if isinstance(mark, dict):
                mark_data = {
                    "target": mark.get("target"),
                    "occurrence": mark.get("occurrence", 1),
                }
                if "style" in mark:
                    mark_data["style"] = mark["style"]
            lines.append({"text": line.get("text"), "mark": mark_data,
                          "note": line.get("note")})
    return {
        "title": card.get("title"),
        "lines": lines,
        "category": card.get("category"),
        "visibility": card.get("visibility"),
    }


def card_hash(card: Dict[str, Any]) -> str:
    payload = json.dumps(card_content(card), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def strip_hash(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value[7:] if value.startswith("sha256:") else value
