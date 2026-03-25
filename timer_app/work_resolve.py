from __future__ import annotations

from typing import Iterable


def resolve_work_name(text: str, names: Iterable[str]) -> str:
    """Best match: exact (case-insensitive), then startswith, then substring; else stripped text."""
    text = text.strip()
    if not text:
        return ""
    names = list(names)
    t = text.lower()
    for n in names:
        if n.lower() == t:
            return n
    for n in names:
        if n.lower().startswith(t):
            return n
    for n in names:
        if t in n.lower():
            return n
    return text
