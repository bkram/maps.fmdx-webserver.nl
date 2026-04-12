"""Core application package for the FMDX statistics service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["create_app"]


if TYPE_CHECKING:
    from flask import Flask


def create_app(*args: Any, **kwargs: Any) -> "Flask":
    """Return a configured Flask application instance.

    Importing :mod:`fmdx_statistics.app` eagerly when the package loads caused
    ``python -m fmdx_statistics.app`` to emit a runtime warning because the
    module was already present in :data:`sys.modules`.  Import lazily so the
    package can be safely used both as ``python -m`` entry point and as a
    library.

    Parameters
    ----------
    *args, **kwargs:
        Forwarded to :func:`fmdx_statistics.app.create_app` unchanged so the
        caller keeps the same entry-point API.
    """

    from .app import create_app as _create_app

    return _create_app(*args, **kwargs)
