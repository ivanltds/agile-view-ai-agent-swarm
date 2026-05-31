"""Metrics Calculator Agent — computes efficiency KPIs.

Numeric computation is deterministic. After computing metrics, the agent asks
Claude for a short narrative paragraph interpreting the numbers.
"""
from __future__ import annotations

from datetime import datetime

from anthropic import AsyncAnthropic

from src.agents.base import BaseAgent
from src.config import CLAUDE_MODEL
from src.models.schemas import (
    AnalyzedPayload,
    AnalyzedWorkItem,
    MetricsPayload,
    RawPayload,
)


def _days_between(a: datetime | None, b: datetime | None) -> float | None:
    if not a or not b:
        return None
    delta = (b - a).total_seconds() / 86400.0
    return delta if delta >= 0 else None


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return round(ordered[lo], 2)
    frac = k - lo
    return round(ordered[lo] * (1 - frac) + ordered[hi] * frac, 2)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


class MetricsCalculator(BaseAgent):
    name = "metrics_calculator"
    description = "Computes Lead Time, Cycle Time, Throughput, Bug Rate, etc."

    def __init__(self, client: AsyncAnthropic) -> None:
        self.client = client

    async def run(self, raw: RawPayload, analyzed: AnalyzedPayload) -> MetricsPayload:
        items = analyzed.items
        closed = [i for i in items if i.state == "Closed"]

        lead_times = [
            d for i in closed if (d := _days_between(i.created_date, i.closed_date))
        ]
        cycle_times = [
            d for i in closed if (d := _days_between(i.active_date, i.closed_date))
        ]

        throughput, delivered, planned = self._per_sprint(raw, items)

        total = len(items) or 1
        bugs = sum(1 for i in items if i.type == "Bug" and i.state != "Removed")
        reopened = sum(1 for i in closed if i.reopened)
        unestimated = sum(1 for i in items if i.unestimated)

        metrics = MetricsPayload(
            lead_time_avg_days=_avg(lead_times),
            lead_time_p85_days=_percentile(lead_times, 0.85),
            cycle_time_avg_days=_avg(cycle_times),
            cycle_time_p85_days=_percentile(cycle_times, 0.85),
            throughput_per_sprint=throughput,
            throughput_avg=_avg([float(t) for t in throughput]),
            bug_rate_pct=round(bugs / total * 100, 1),
            reopen_rate_pct=round(reopened / (len(closed) or 1) * 100, 1),
            unestimated_pct=round(unestimated / total * 100, 1),
            story_points_delivered=delivered,
            story_points_planned=planned,
        )
        metrics.narrative = await self._narrative(metrics, raw)
        return metrics

    def _per_sprint(
        self, raw: RawPayload, items: list[AnalyzedWorkItem]
    ) -> tuple[list[int], list[float], list[float]]:
        by_id = {i.id: i for i in items}
        throughput: list[int] = []
        delivered: list[float] = []
        planned: list[float] = []
        for it in raw.iterations:
            start, end = it.start_date, it.finish_date
            closed_count = 0
            delivered_pts = 0.0
            planned_pts = 0.0
            for wid in it.item_ids:
                item = by_id.get(wid)
                if not item:
                    continue
                planned_pts += item.story_points or 0.0
                if item.state == "Closed" and item.closed_date and start and end:
                    if start <= item.closed_date.date() <= end:
                        closed_count += 1
                        delivered_pts += item.story_points or 0.0
            throughput.append(closed_count)
            delivered.append(round(delivered_pts, 1))
            planned.append(round(planned_pts, 1))
        return throughput, delivered, planned

    async def _narrative(self, metrics: MetricsPayload, raw: RawPayload) -> str:
        prompt = (
            "Write one concise paragraph (no headers, no bullet points) "
            "interpreting these Azure Boards efficiency metrics in context. "
            f"Team size: {len(raw.team_members)}. "
            f"Work items analyzed: {raw.metadata.items_in_range}. "
            f"Sprints: {raw.metadata.sprints_analyzed}.\n"
            f"Lead time avg/p85: {metrics.lead_time_avg_days}/{metrics.lead_time_p85_days} days. "
            f"Cycle time avg/p85: {metrics.cycle_time_avg_days}/{metrics.cycle_time_p85_days} days. "
            f"Throughput avg: {metrics.throughput_avg}/sprint. "
            f"Bug rate: {metrics.bug_rate_pct}%. "
            f"Reopen rate: {metrics.reopen_rate_pct}%. "
            f"Unestimated: {metrics.unestimated_pct}%."
        )
        try:
            resp = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except Exception:
            return (
                f"Across {raw.metadata.items_in_range} work items, the team averaged "
                f"{metrics.throughput_avg} closed items per sprint with a mean lead time "
                f"of {metrics.lead_time_avg_days} days and a bug rate of "
                f"{metrics.bug_rate_pct}%."
            )
