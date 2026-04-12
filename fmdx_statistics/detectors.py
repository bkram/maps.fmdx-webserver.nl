"""Helpers for classifying receiver metadata."""

from __future__ import annotations

from typing import Optional


def os_family(value: Optional[str]) -> str:
    """Map free-form OS strings into coarse families."""

    text = str(value or "").strip().lower()
    if not text:
        return "Unknown"
    if "windows" in text or " nt" in text:
        return "Windows"
    if "linux" in text:
        return "Linux"
    if "darwin" in text or "mac" in text or "os x" in text:
        return "macOS"
    if "freebsd" in text:
        return "FreeBSD"
    if "openbsd" in text:
        return "OpenBSD"
    if "android" in text:
        return "Android"
    return "Other"


def is_windows_family(value: Optional[str]) -> bool:
    """Return ``True`` when *value* refers to a Windows OS."""

    return os_family(value) == "Windows"
