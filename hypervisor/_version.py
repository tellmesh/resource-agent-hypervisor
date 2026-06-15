"""
Single source of truth for package version at runtime.

Tries PEP 566 / importlib.metadata first (when installed),
falls back to a development default.
"""

from __future__ import annotations

__all__ = ["__version__"]

try:
    from importlib.metadata import version, PackageNotFoundError

    try:
        __version__ = version("hypervisor")
    except PackageNotFoundError:
        __version__ = "0.1.0.dev0"
except Exception:  # pragma: no cover
    __version__ = "0.1.0.dev0"
