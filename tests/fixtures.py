"""Test fixtures: builders for raw and analyzed payloads."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src.models.schemas import (
    AnalyzedPayload,
    AnalyzedWorkItem,
    Iteration,
    ProjectMetadata,
    RawPayload,
    RawWorkItem,
    TeamMember,
)

_NOW = datetime(2026, 5, 15, tzinfo=timezone.utc)


def make_raw_payload() -> RawPayload:
    created = _NOW - timedelta(days=20)
    active = _NOW - timedelta(days=15)
    closed = _NOW - timedelta(days=5)
    work_items = [
        RawWorkItem(
            id=1, work_item_type="User Story", title="Login", state="Done",
            assigned_to="Alice", story_points=5,
            created_date=created, activated_date=active, closed_date=closed,
        ),
        RawWorkItem(
            id=2, work_item_type="Bug", title="Crash", state="Active",
            assigned_to="Bob", story_points=3, tags=["Blocked"],
            created_date=created, activated_date=active,
        ),
        RawWorkItem(
            id=3, work_item_type="Task", title="Refactor", state="Doing",
            assigned_to="Alice", story_points=None, created_date=created,
        ),
    ]
    iteration = Iteration(
        id="it1", name="Sprint 1",
        start_date=date(2026, 5, 1), finish_date=date(2026, 5, 14),
        item_ids=[1, 2, 3],
    )
    members = [
        TeamMember(id="a", display_name="Alice"),
        TeamMember(id="b", display_name="Bob"),
    ]
    meta = ProjectMetadata(
        org="acme", project="MyProject", team="TeamAlpha",
        generated_at=_NOW, sprints_analyzed=1, items_in_range=len(work_items),
    )
    return RawPayload(
        work_items=work_items, iterations=[iteration],
        team_members=members, metadata=meta,
    )


def make_analyzed_payload() -> AnalyzedPayload:
    created = _NOW - timedelta(days=20)
    active = _NOW - timedelta(days=15)
    closed = _NOW - timedelta(days=5)
    items = [
        AnalyzedWorkItem(id=1, type="UserStory", state="Closed", title="Login",
                         assigned_to="Alice", story_points=5,
                         created_date=created, active_date=active, closed_date=closed),
        AnalyzedWorkItem(id=2, type="Bug", state="Active", title="Crash",
                         assigned_to="Bob", story_points=3, blocked=True,
                         created_date=created, active_date=active),
        AnalyzedWorkItem(id=3, type="Task", state="Active", title="Refactor",
                         assigned_to="Alice", unestimated=True, created_date=created),
    ]
    return AnalyzedPayload(
        items=items, blocked_items=["2"], unestimated_items=["3"],
        state_map={"Done": "Closed", "Doing": "Active", "Active": "Active"},
    )
