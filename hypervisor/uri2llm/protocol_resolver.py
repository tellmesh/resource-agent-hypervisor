"""Deprecated: use uri3.resolvers.protocol_resolver instead."""

from uri3.resolvers.protocol_resolver import (
    resolve_a2a,
    resolve_http_like,
    resolve_mcp,
    resolve_resource,
)

__all__ = ["resolve_http_like", "resolve_a2a", "resolve_mcp", "resolve_resource"]
