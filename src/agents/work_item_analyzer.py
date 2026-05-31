"""Work Item Analyzer Agent — classifies and normalizes raw work items.

Uses the Claude API to resolve ambiguous custom state names into canonical
states. All other logic is deterministic.
"""
from __future__ import annotations

import json

from anthropic import AsyncAnthropic

from src.agents.base import BaseAgent
from src.config import CLAUDE_MODEL
from src.models.schemas import (
    CANONICAL_STATES,
    AnalyzedPayload,
    AnalyzedWorkItem,
    RawPayload,
    RawWorkItem,
)
from src.tools.json_utils import extract_json

_TYPE_MAP = {
    "epic": "Epic",
    "feature": "Feature",
    "user story": "UserStory",
    "userstory": "UserStory",
    "story": "UserStory",
    "product backlog item": "UserStory",
    "task": "Task",
    "bug": "Bug",
}

# Built-in fallbacks so the agent works even if the Claude call fails.
_STATE_FALLBACK = {
    "new": "New",
    "to do": "New",
    "approved": "New",
    "proposed": "New",
    "active": "Active",
    "doing": "Active",
    "in progress": "Active",
    "in review": "Active",
    "committed": "Active",
    "blocked": "Active",
    "resolved": "Resolved",
    "ready for qa": "Resolved",
    "in test": "Resolved",
    "done": "Closed",
    "closed": "Closed",
    "completed": "Closed",
    "removed": "Removed",
}

_SYSTEM = (
    "You are a work item state classifier for Azure DevOps. "
    "Map the given custom state names to canonical states: "
    "New, Active, Resolved, Closed, Removed. "
    'Respond only with a JSON object: {"custom_state": "canonical_state", ...}'
)


class WorkItemAnalyzer(BaseAgent):
    name = "work_item_analyzer"
    description = "Classifies work items into canonical types and states."

    def __init__(self, client: AsyncAnthropic) -> None:
        self.client = client

    async def run(self, raw: RawPayload) -> AnalyzedPayload:
        state_names = sorted({wi.state for wi in raw.work_items if wi.state})
        state_map = await self._resolve_states(state_names)

        items: list[AnalyzedWorkItem] = []
        blocked: list[str] = []
        unestimated: list[str] = []
        for wi in raw.work_items:
            item = self._classify(wi, state_map)
            items.append(item)
            if item.blocked:
                blocked.append(str(item.id))
            if item.unestimated:
                unestimated.append(str(item.id))

        return AnalyzedPayload(
            items=items,
            blocked_items=blocked,
            unestimated_items=unestimated,
            state_map=state_map,
        )

    # ── Claude-assisted state resolution ────────────────────────────────────
    async def _resolve_states(self, state_names: list[str]) -> dict[str, str]:
        fallback = {s: self._fallback_state(s) for s in state_names}
        if not state_names:
            return fallback
        try:
            resp = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "These are the state names found in this project:\n"
                            f"{json.dumps(state_names)}"
                        ),
                    }
                ],
            )
            parsed = extract_json(resp.content[0].text)
            result: dict[str, str] = {}
            for name in state_names:
                canon = parsed.get(name)
                result[name] = canon if canon in CANONICAL_STATES else fallback[name]
            return result
        except Exception:
            return fallback

    @staticmethod
    def _fallback_state(name: str) -> str:
        return _STATE_FALLBACK.get(name.strip().lower(), "Active")

    # ── Deterministic classification ────────────────────────────────────────
    def _classify(self, wi: RawWorkItem, state_map: dict[str, str]) -> AnalyzedWorkItem:
        ctype = _TYPE_MAP.get(wi.work_item_type.strip().lower(), "Other")
        cstate = state_map.get(wi.state, self._fallback_state(wi.state))

        tags_lower = {t.lower() for t in wi.tags}
        blocked = "blocked" in tags_lower or wi.state.strip().lower() == "blocked"

        unestimated = ctype in ("UserStory", "Task") and not wi.story_points

        reopened = self._was_reopened(wi)

        return AnalyzedWorkItem(
            id=wi.id,
            type=ctype,
            state=cstate,
            title=wi.title,
            assigned_to=wi.assigned_to,
            story_points=wi.story_points,
            blocked=blocked,
            unestimated=unestimated,
            created_date=wi.created_date,
            active_date=wi.activated_date,
            closed_date=wi.closed_date,
            reopened=reopened,
            iteration_path=wi.iteration_path,
        )

    @staticmethod
    def _was_reopened(wi: RawWorkItem) -> bool:
        # If an item was activated *after* it was closed, it was reopened.
        if wi.activated_date and wi.closed_date:
            return wi.activated_date > wi.closed_date
        # Otherwise inspect the recorded state history if present.
        seen_closed = False
        for state, _ts in wi.state_history:
            canon = _STATE_FALLBACK.get(state.strip().lower(), "")
            if canon == "Closed":
                seen_closed = True
            elif seen_closed and canon in ("Active", "New"):
                return True
        return False
