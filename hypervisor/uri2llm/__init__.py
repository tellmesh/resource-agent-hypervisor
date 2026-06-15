"""Deprecated: use uri3.resolvers.router instead."""

from __future__ import annotations

import warnings

from uri3.resolvers.router import UriResolution, call, resolve

warnings.warn(
    "hypervisor.uri2llm is deprecated; use uri3.resolvers.router instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["resolve", "call", "UriResolution"]
