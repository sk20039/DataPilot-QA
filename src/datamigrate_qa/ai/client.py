"""Anthropic client with soft import and API key validation."""
from __future__ import annotations

import os
from typing import Any

_ANTHROPIC_AVAILABLE = False

try:
    import anthropic as _anthropic  # noqa: F401
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    pass

_cached_client: Any = None


def get_client() -> Any:
    """Return a cached Anthropic client.

    Raises RuntimeError if anthropic is not installed or API key is missing.
    """
    global _cached_client
    if not _ANTHROPIC_AVAILABLE:
        raise RuntimeError(
            "AI features require the 'anthropic' package. "
            "Install with: pip install -e '.[ai]'"
        )
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "AI features require the ANTHROPIC_API_KEY environment variable to be set."
        )
    if _cached_client is None:
        import anthropic
        _cached_client = anthropic.Anthropic(api_key=api_key)
    return _cached_client


def is_available() -> bool:
    """Return True if AI features can be used (package installed + key set)."""
    return _ANTHROPIC_AVAILABLE and bool(os.environ.get("ANTHROPIC_API_KEY"))
