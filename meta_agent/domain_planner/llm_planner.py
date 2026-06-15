"""Deprecated: use nl2uri.domain_planner instead."""

from __future__ import annotations

import warnings

from nl2uri.domain_planner import plan_domain_from_prompt, plan_from_prompt

warnings.warn(
    "meta_agent.domain_planner.llm_planner is deprecated; use nl2uri.domain_planner instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["plan_domain_from_prompt", "plan_from_prompt"]
