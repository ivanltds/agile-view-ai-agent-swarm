"""Report Generator Agent — assembles the final self-contained HTML report.

Renders templates/report.html.j2 with Jinja2. Asks Claude to write the
Recommendations section based on the full aggregated payload.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from src.tools.ai_client import AIClient

from src.agents.base import BaseAgent
from src.models.schemas import AggregatedPayload
from src.tools.html_builder import render_report


class ReportGenerator(BaseAgent):
    name = "report_generator"
    description = "Builds the final HTML efficiency report."

    def __init__(self, client: AIClient) -> None:
        self.client = client

    async def run(self, agg: AggregatedPayload) -> str:
        agg.recommendations = await self._recommendations(agg)
        context = self._build_context(agg)
        return render_report(context)

    # ── Context assembly ────────────────────────────────────────────────────
    def _build_context(self, agg: AggregatedPayload) -> dict:
        items = agg.analyzed.items
        type_counts = Counter(i.type for i in items)
        state_counts = Counter(i.state for i in items)

        per_member: dict[str, dict] = defaultdict(lambda: {"items": 0, "points": 0.0})
        for i in items:
            who = i.assigned_to or "Unassigned"
            per_member[who]["items"] += 1
            per_member[who]["points"] += i.story_points or 0.0
        team_breakdown = [
            {"name": k, "items": v["items"], "points": round(v["points"], 1)}
            for k, v in sorted(per_member.items(), key=lambda kv: -kv[1]["items"])
        ]

        item_by_id = {i.id: i for i in items}
        at_risk = []
        for iid in set(agg.analyzed.blocked_items) | set(agg.analyzed.unestimated_items):
            i = item_by_id.get(int(iid))
            if not i:
                continue
            reasons = []
            if i.blocked:
                reasons.append("Blocked")
            if i.unestimated:
                reasons.append("No estimate")
            at_risk.append(
                {"id": i.id, "title": i.title, "type": i.type, "reasons": ", ".join(reasons)}
            )

        velocity_data = {
            "labels": [v.sprint_name for v in agg.sprint.velocity_per_sprint],
            "datasets": [
                {
                    "label": "Delivered",
                    "data": [v.delivered_points for v in agg.sprint.velocity_per_sprint],
                },
                {
                    "label": "Planned",
                    "data": [v.planned_points for v in agg.sprint.velocity_per_sprint],
                },
            ],
        }
        burndown_data = {
            "labels": [str(p.date) for p in agg.sprint.current_burndown],
            "datasets": [
                {
                    "label": "Remaining",
                    "data": [p.remaining_points for p in agg.sprint.current_burndown],
                },
                {
                    "label": "Ideal",
                    "data": [p.ideal_remaining for p in agg.sprint.current_burndown],
                },
            ],
        }

        return {
            "meta": agg.raw.metadata,
            "metrics": agg.metrics,
            "sprint": agg.sprint,
            "type_counts": dict(type_counts),
            "state_counts": dict(state_counts),
            "team_breakdown": team_breakdown,
            "at_risk": at_risk,
            "recommendations": agg.recommendations,
            "unavailable_sections": agg.unavailable_sections,
            "velocity_data": velocity_data,
            "burndown_data": burndown_data,
        }

    # ── Recommendations via Claude ──────────────────────────────────────────
    async def _recommendations(self, agg: AggregatedPayload) -> str:
        m = agg.metrics
        prompt = (
            "Based on the following Azure Boards efficiency data, write 3 to 5 "
            "concrete, actionable recommendations for the team. Return them as an "
            "HTML unordered list (<ul><li>...</li></ul>) and nothing else.\n\n"
            f"Lead time avg/p85: {m.lead_time_avg_days}/{m.lead_time_p85_days} d. "
            f"Cycle time avg/p85: {m.cycle_time_avg_days}/{m.cycle_time_p85_days} d. "
            f"Throughput avg: {m.throughput_avg}. Bug rate: {m.bug_rate_pct}%. "
            f"Reopen rate: {m.reopen_rate_pct}%. Unestimated: {m.unestimated_pct}%. "
            f"Velocity trend: {agg.sprint.velocity_trend}. "
            f"Blocked items: {len(agg.analyzed.blocked_items)}. "
            f"Metrics narrative: {m.narrative} "
            f"Sprint insights: {agg.sprint.insights}"
        )
        try:
            resp = await self.client.messages.create(
                model=self.client.default_model,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            return text if "<li>" in text else f"<ul><li>{text}</li></ul>"
        except Exception:
            return (
                "<ul>"
                "<li>Reduce work-in-progress to lower cycle time.</li>"
                "<li>Estimate all stories and tasks before sprint start.</li>"
                "<li>Investigate and unblock the flagged at-risk items.</li>"
                "</ul>"
            )
