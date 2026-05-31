"""Data Fetcher Agent — retrieves all raw data from Azure DevOps.

This is the only agent (besides the Orchestrator's validation step) that makes
external HTTP calls. All logic is deterministic; it does not use the Claude API.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from src.agents.base import BaseAgent
from src.config import WIQL_PAGE_SIZE
from src.models.schemas import (
    Iteration,
    ProjectMetadata,
    RawPayload,
    RawWorkItem,
    TeamMember,
)
from src.tools.azure_api import AzureClient


@dataclass
class FetcherInput:
    org: str
    project: str
    team: str
    pat: str
    sprints_back: int = 5
    batch_size: int = 50


WIQL = """
SELECT [System.Id]
FROM WorkItems
WHERE [System.TeamProject] = @project
  AND [System.AreaPath] UNDER @project
  AND [System.ChangedDate] >= @today - {days}
ORDER BY [System.ChangedDate] DESC
""".strip()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class DataFetcher(BaseAgent):
    name = "data_fetcher"
    description = "Retrieves work items, iterations and members from Azure DevOps."

    def __init__(self, client: AzureClient) -> None:
        self.client = client

    async def run(self, payload: FetcherInput) -> RawPayload:
        days = max(payload.sprints_back, 1) * 18  # ~avg sprint length in days
        ids = await self._wiql_ids(payload.project, days)
        work_items, iterations, members = await asyncio.gather(
            self._fetch_items(payload.project, ids, payload.batch_size),
            self._fetch_iterations(payload.project, payload.team, payload.sprints_back),
            self._fetch_members(payload.project, payload.team),
        )
        metadata = ProjectMetadata(
            org=payload.org,
            project=payload.project,
            team=payload.team,
            generated_at=datetime.now(timezone.utc),
            sprints_analyzed=payload.sprints_back,
            items_in_range=len(work_items),
        )
        return RawPayload(
            work_items=work_items,
            iterations=iterations,
            team_members=members,
            metadata=metadata,
        )

    # ── WIQL ────────────────────────────────────────────────────────────────
    async def _wiql_ids(self, project: str, days: int) -> list[int]:
        body = {"query": WIQL.format(days=days)}
        data = await self.client.post(
            "_apis/wit/wiql", project=project, json=body
        )
        ids = [w["id"] for w in data.get("workItems", [])]
        return ids[: WIQL_PAGE_SIZE * 10]  # safety cap across pages

    # ── Work items (batched, concurrent) ────────────────────────────────────
    async def _fetch_items(
        self, project: str, ids: list[int], batch_size: int
    ) -> list[RawWorkItem]:
        if not ids:
            return []
        chunks = [ids[i : i + batch_size] for i in range(0, len(ids), batch_size)]
        results = await asyncio.gather(
            *(self._fetch_batch(project, chunk) for chunk in chunks)
        )
        items: list[RawWorkItem] = []
        for batch in results:
            items.extend(batch)
        return items

    async def _fetch_batch(self, project: str, chunk: list[int]) -> list[RawWorkItem]:
        body = {
            "ids": chunk,
            "fields": [
                "System.Id",
                "System.WorkItemType",
                "System.Title",
                "System.State",
                "System.AssignedTo",
                "System.Tags",
                "System.CreatedDate",
                "Microsoft.VSTS.Common.ActivatedDate",
                "Microsoft.VSTS.Common.ClosedDate",
                "Microsoft.VSTS.Scheduling.StoryPoints",
                "System.IterationPath",
            ],
        }
        data = await self.client.post(
            "_apis/wit/workitemsbatch", project=project, json=body
        )
        return [self._to_raw(w) for w in data.get("value", [])]

    @staticmethod
    def _to_raw(w: dict) -> RawWorkItem:
        f = w.get("fields", {})
        assigned = f.get("System.AssignedTo")
        if isinstance(assigned, dict):
            assigned = assigned.get("displayName")
        tags_raw = f.get("System.Tags") or ""
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()]
        return RawWorkItem(
            id=w["id"],
            work_item_type=f.get("System.WorkItemType", "Other"),
            title=f.get("System.Title", ""),
            state=f.get("System.State", ""),
            assigned_to=assigned,
            story_points=f.get("Microsoft.VSTS.Scheduling.StoryPoints"),
            tags=tags,
            created_date=_parse_dt(f.get("System.CreatedDate")),
            activated_date=_parse_dt(f.get("Microsoft.VSTS.Common.ActivatedDate")),
            closed_date=_parse_dt(f.get("Microsoft.VSTS.Common.ClosedDate")),
            iteration_path=f.get("System.IterationPath"),
        )

    # ── Iterations ──────────────────────────────────────────────────────────
    async def _fetch_iterations(
        self, project: str, team: str, sprints_back: int
    ) -> list[Iteration]:
        path = f"{project}/{team}/_apis/work/teamsettings/iterations"
        data = await self.client.get(path)
        iterations: list[Iteration] = []
        for it in data.get("value", []):
            attrs = it.get("attributes", {}) or {}
            iterations.append(
                Iteration(
                    id=it["id"],
                    name=it.get("name", ""),
                    start_date=_date(attrs.get("startDate")),
                    finish_date=_date(attrs.get("finishDate")),
                )
            )
        iterations.sort(key=lambda i: (i.start_date is None, i.start_date))
        recent = iterations[-sprints_back:] if sprints_back else iterations
        await asyncio.gather(
            *(self._fill_iteration_items(project, team, it) for it in recent)
        )
        return recent

    async def _fill_iteration_items(
        self, project: str, team: str, iteration: Iteration
    ) -> None:
        path = f"{project}/{team}/_apis/work/teamsettings/iterations/{iteration.id}/workitems"
        try:
            data = await self.client.get(path)
        except Exception:
            return
        rels = data.get("workItemRelations", [])
        iteration.item_ids = [
            r["target"]["id"] for r in rels if r.get("target", {}).get("id")
        ]

    # ── Members ─────────────────────────────────────────────────────────────
    async def _fetch_members(self, project: str, team: str) -> list[TeamMember]:
        path = f"_apis/projects/{project}/teams/{team}/members"
        data = await self.client.get(path)
        members: list[TeamMember] = []
        for m in data.get("value", []):
            identity = m.get("identity", m)
            members.append(
                TeamMember(
                    id=identity.get("id", ""),
                    display_name=identity.get("displayName", ""),
                    unique_name=identity.get("uniqueName"),
                )
            )
        return members


def _date(value: str | None):
    dt = _parse_dt(value)
    return dt.date() if dt else None
