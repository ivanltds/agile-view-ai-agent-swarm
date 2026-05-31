"""Sprint Analyzer Agent — velocity history and current sprint burndown.

Computation is deterministic; Claude provides a short insight block describing
patterns across sprints.
"""
from __future__ import annotations

from datetime import date, timedelta

from anthropic import AsyncAnthropic

from src.agents.base import BaseAgent
from src.config import CLAUDE_MODEL
from src.models.schemas import (
    AnalyzedPayload,
    AnalyzedWorkItem,
    BurndownPoint,
    Iteration,
    RawPayload,
    SprintPayload,
    SprintVelocity,
)


class SprintAnalyzer(BaseAgent):
    name = "sprint_analyzer"
    description = "Computes velocity per sprint and current-sprint burndown."

    def __init__(self, client: AsyncAnthropic) -> None:
        self.client = client

    async def run(self, raw: RawPayload, analyzed: AnalyzedPayload) -> SprintPayload:
        by_id = {i.id: i for i in analyzed.items}
        velocity = [self._velocity(it, by_id) for it in raw.iterations]

        current = self._current_sprint(raw.iterations)
        burndown = self._burndown(current, by_id) if current else []

        delivered = [v.delivered_points for v in velocity]
        velocity_avg = round(sum(delivered) / len(delivered), 1) if delivered else 0.0
        trend = self._trend(delivered)

        payload = SprintPayload(
            velocity_per_sprint=velocity,
            current_burndown=burndown,
            current_sprint=current,
            velocity_avg=velocity_avg,
            velocity_trend=trend,
        )
        payload.insights = await self._insights(velocity, trend)
        return payload

    def _velocity(
        self, it: Iteration, by_id: dict[int, AnalyzedWorkItem]
    ) -> SprintVelocity:
        planned = 0.0
        delivered = 0.0
        count = 0
        for wid in it.item_ids:
            item = by_id.get(wid)
            if not item:
                continue
            planned += item.story_points or 0.0
            if (
                item.state == "Closed"
                and item.closed_date
                and it.start_date
                and it.finish_date
                and it.start_date <= item.closed_date.date() <= it.finish_date
            ):
                delivered += item.story_points or 0.0
                count += 1
        return SprintVelocity(
            sprint_name=it.name,
            sprint_start=it.start_date,
            sprint_end=it.finish_date,
            planned_points=round(planned, 1),
            delivered_points=round(delivered, 1),
            item_count=count,
        )

    @staticmethod
    def _current_sprint(iterations: list[Iteration]) -> Iteration | None:
        today = date.today()
        for it in iterations:
            if it.start_date and it.finish_date and it.start_date <= today <= it.finish_date:
                return it
        # fall back to the most recent sprint with dates
        dated = [it for it in iterations if it.finish_date]
        return dated[-1] if dated else (iterations[-1] if iterations else None)

    def _burndown(
        self, sprint: Iteration, by_id: dict[int, AnalyzedWorkItem]
    ) -> list[BurndownPoint]:
        if not sprint.start_date or not sprint.finish_date:
            return []
        items = [by_id[w] for w in sprint.item_ids if w in by_id]
        total = sum(i.story_points or 0.0 for i in items)
        days = (sprint.finish_date - sprint.start_date).days
        if days <= 0:
            return []
        points: list[BurndownPoint] = []
        for offset in range(days + 1):
            day = sprint.start_date + timedelta(days=offset)
            burned = sum(
                i.story_points or 0.0
                for i in items
                if i.state == "Closed" and i.closed_date and i.closed_date.date() <= day
            )
            ideal = total * (1 - offset / days)
            points.append(
                BurndownPoint(
                    date=day,
                    remaining_points=round(total - burned, 1),
                    ideal_remaining=round(max(ideal, 0.0), 1),
                    is_weekend=day.weekday() >= 5,
                )
            )
        return points

    @staticmethod
    def _trend(delivered: list[float]) -> str:
        if len(delivered) < 2:
            return "stable"
        first = sum(delivered[: len(delivered) // 2]) or 0.0
        second = sum(delivered[len(delivered) // 2 :]) or 0.0
        if second > first * 1.1:
            return "improving"
        if second < first * 0.9:
            return "declining"
        return "stable"

    async def _insights(self, velocity: list[SprintVelocity], trend: str) -> str:
        summary = ", ".join(
            f"{v.sprint_name}: {v.delivered_points}/{v.planned_points}pts" for v in velocity
        )
        prompt = (
            "Given this sprint velocity history (delivered/planned story points), "
            "write 2-3 concise sentences identifying patterns "
            "(e.g. consistent under-delivery, volatility, correlation with sprint position). "
            "No headers or bullet points.\n"
            f"Trend classification: {trend}.\n"
            f"Data: {summary}"
        )
        try:
            resp = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except Exception:
            return f"Velocity trend is {trend} across {len(velocity)} sprints."
