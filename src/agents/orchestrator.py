"""Orchestrator Agent — entry point and coordinator of the swarm.

Pure Python: validates inputs, sequences execution phases, aggregates results.
It does not use the Claude API itself.
"""
from __future__ import annotations

import logging
from datetime import datetime

from anthropic import AsyncAnthropic

from src.agents.base import BaseAgent
from src.agents.data_fetcher import DataFetcher, FetcherInput
from src.agents.metrics_calculator import MetricsCalculator
from src.agents.report_generator import ReportGenerator
from src.agents.sprint_analyzer import SprintAnalyzer
from src.agents.work_item_analyzer import WorkItemAnalyzer
from src.models.schemas import (
    AggregatedPayload,
    AnalyzedPayload,
    MetricsPayload,
    SprintPayload,
)
from src.tools.azure_api import AzureAPIError, AzureClient

log = logging.getLogger("swarm.orchestrator")


class OrchestratorError(Exception):
    """Unrecoverable error during orchestration."""


class Orchestrator(BaseAgent):
    name = "orchestrator"
    description = "Coordinates the agent swarm end to end."

    def __init__(self, anthropic: AsyncAnthropic, azure: "AzureClient") -> None:
        self.anthropic = anthropic
        self.azure = azure

    # ── Validation (Phase 1) ────────────────────────────────────────────────
    async def validate(self, org: str, project: str, team: str) -> dict:
        if not org or not project or not team:
            raise OrchestratorError("org, project and team are all required")
        try:
            proj = await self.azure.get(f"_apis/projects/{project}")
        except Exception as exc:  # noqa: BLE001
            raise OrchestratorError(f"Project validation failed: {exc}") from exc
        try:
            members = await self.azure.get(
                f"_apis/projects/{project}/teams/{team}/members"
            )
        except Exception as exc:  # noqa: BLE001
            raise OrchestratorError(f"Team validation failed: {exc}") from exc
        return {
            "project": proj.get("name", project),
            "member_count": len(members.get("value", [])),
        }

    # ── Full run (Phases 2-4) ───────────────────────────────────────────────
    async def run(
        self, org: str, project: str, team: str, pat: str, sprints: int, batch_size: int
    ) -> AggregatedPayload:
        await self.validate(org, project, team)

        fetcher = DataFetcher(self.azure)
        raw = await fetcher.run(
            FetcherInput(
                org=org,
                project=project,
                team=team,
                pat=pat,
                sprints_back=sprints,
                batch_size=batch_size,
            )
        )
        if not raw.work_items:
            log.warning("No work items found in range; producing partial report.")

        analyzer = WorkItemAnalyzer(self.anthropic)
        metrics_agent = MetricsCalculator(self.anthropic)
        sprint_agent = SprintAnalyzer(self.anthropic)

        unavailable: list[str] = []

        # Work Item Analyzer must run first (others depend on its output).
        try:
            analyzed = await analyzer.run(raw)
        except Exception as exc:  # noqa: BLE001
            log.warning("Work Item Analyzer failed: %s", exc)
            analyzed = AnalyzedPayload(items=[])
            unavailable.append("analysis")

        import asyncio

        metrics_res, sprint_res = await asyncio.gather(
            metrics_agent.run(raw, analyzed),
            sprint_agent.run(raw, analyzed),
            return_exceptions=True,
        )
        if isinstance(metrics_res, Exception):
            log.warning("Metrics Calculator failed: %s", metrics_res)
            metrics_res = MetricsPayload()
            unavailable.append("metrics")
        if isinstance(sprint_res, Exception):
            log.warning("Sprint Analyzer failed: %s", sprint_res)
            sprint_res = SprintPayload()
            unavailable.append("sprint")

        return AggregatedPayload(
            raw=raw,
            analyzed=analyzed,
            metrics=metrics_res,
            sprint=sprint_res,
            unavailable_sections=unavailable,
        )

    async def generate_report(self, agg: AggregatedPayload) -> str:
        generator = ReportGenerator(self.anthropic)
        return await generator.run(agg)

    @staticmethod
    def output_filename(project: str, team: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = lambda s: s.replace(" ", "_")  # noqa: E731
        return f"report_{safe(project)}_{safe(team)}_{ts}.html"
