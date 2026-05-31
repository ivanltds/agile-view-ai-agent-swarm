"""Pydantic v2 data models exchanged between agents.

The Orchestrator passes these objects from agent to agent. Keeping every
schema here makes agents independently testable and the data contracts
explicit.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

# Canonical work item types and states ---------------------------------------
CANONICAL_TYPES = ("Epic", "Feature", "UserStory", "Task", "Bug", "Other")
CANONICAL_STATES = ("New", "Active", "Resolved", "Closed", "Removed")


# ── Raw layer (Data Fetcher output) ─────────────────────────────────────────
class TeamMember(BaseModel):
    id: str
    display_name: str
    unique_name: str | None = None


class Iteration(BaseModel):
    id: str
    name: str
    start_date: date | None = None
    finish_date: date | None = None
    item_ids: list[int] = Field(default_factory=list)


class RawWorkItem(BaseModel):
    id: int
    work_item_type: str
    title: str = ""
    state: str = ""
    assigned_to: str | None = None
    story_points: float | None = None
    tags: list[str] = Field(default_factory=list)
    created_date: datetime | None = None
    activated_date: datetime | None = None
    closed_date: datetime | None = None
    iteration_path: str | None = None
    # raw revision states: list of (state, timestamp)
    state_history: list[tuple[str, datetime]] = Field(default_factory=list)


class ProjectMetadata(BaseModel):
    org: str
    project: str
    team: str
    generated_at: datetime
    sprints_analyzed: int
    items_in_range: int


class RawPayload(BaseModel):
    work_items: list[RawWorkItem]
    iterations: list[Iteration]
    team_members: list[TeamMember]
    metadata: ProjectMetadata


# ── Analyzed layer (Work Item Analyzer output) ──────────────────────────────
class AnalyzedWorkItem(BaseModel):
    id: int
    type: str               # canonical type
    state: str              # canonical state
    title: str = ""
    assigned_to: str | None = None
    story_points: float | None = None
    blocked: bool = False
    unestimated: bool = False
    created_date: datetime | None = None
    active_date: datetime | None = None
    closed_date: datetime | None = None
    reopened: bool = False
    iteration_path: str | None = None


class AnalyzedPayload(BaseModel):
    items: list[AnalyzedWorkItem]
    blocked_items: list[str] = Field(default_factory=list)
    unestimated_items: list[str] = Field(default_factory=list)
    state_map: dict[str, str] = Field(default_factory=dict)


# ── Metrics layer ───────────────────────────────────────────────────────────
class MetricsPayload(BaseModel):
    lead_time_avg_days: float = 0.0
    lead_time_p85_days: float = 0.0
    cycle_time_avg_days: float = 0.0
    cycle_time_p85_days: float = 0.0
    throughput_per_sprint: list[int] = Field(default_factory=list)
    throughput_avg: float = 0.0
    bug_rate_pct: float = 0.0
    reopen_rate_pct: float = 0.0
    unestimated_pct: float = 0.0
    story_points_delivered: list[float] = Field(default_factory=list)
    story_points_planned: list[float] = Field(default_factory=list)
    narrative: str = ""


# ── Sprint layer ────────────────────────────────────────────────────────────
class SprintVelocity(BaseModel):
    sprint_name: str
    sprint_start: date | None = None
    sprint_end: date | None = None
    planned_points: float = 0.0
    delivered_points: float = 0.0
    item_count: int = 0


class BurndownPoint(BaseModel):
    date: date
    remaining_points: float
    ideal_remaining: float
    is_weekend: bool = False


class SprintPayload(BaseModel):
    velocity_per_sprint: list[SprintVelocity] = Field(default_factory=list)
    current_burndown: list[BurndownPoint] = Field(default_factory=list)
    current_sprint: Iteration | None = None
    velocity_avg: float = 0.0
    velocity_trend: str = "stable"   # improving | stable | declining
    insights: str = ""


# ── Aggregate ───────────────────────────────────────────────────────────────
class AggregatedPayload(BaseModel):
    raw: RawPayload
    analyzed: AnalyzedPayload
    metrics: MetricsPayload
    sprint: SprintPayload
    recommendations: str = ""
    # sections that failed during analysis are listed here and rendered as
    # "unavailable" in the report
    unavailable_sections: list[str] = Field(default_factory=list)
