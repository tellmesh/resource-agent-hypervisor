"""Deprecated: use hypervisor.domain_pack.generator instead."""

from __future__ import annotations

import warnings

from hypervisor.domain_pack.generator import generate_domain_pack_from_tree

warnings.warn(
    "meta_agent.domain_planner.domain_pack_generator is deprecated; "
    "use hypervisor.domain_pack.generator instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["generate_domain_pack_from_tree"]
