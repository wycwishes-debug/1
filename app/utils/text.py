"""Text utilities."""

from __future__ import annotations

import textwrap


def truncate(text: str, width: int) -> str:
    """Trim text for table display."""

    return text if len(text) <= width else textwrap.shorten(text, width=width, placeholder="…")
