"""Base agent interface shared by every agent in the swarm."""
from __future__ import annotations

from typing import Any


class BaseAgent:
    """Common async interface for all agents.

    Agents are stateless: they receive a payload, do their work, and return a
    result. The Orchestrator owns all state and sequencing.
    """

    name: str = "base"
    description: str = "Base agent"

    async def run(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError
