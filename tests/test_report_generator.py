import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.report_generator import ReportGenerator
from src.models.schemas import AggregatedPayload, MetricsPayload, SprintPayload
from tests.fixtures import make_raw_payload, make_analyzed_payload


@pytest.mark.asyncio
async def test_renders_html():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="<ul><li>Do X</li></ul>")]
    ))
    agg = AggregatedPayload(
        raw=make_raw_payload(),
        analyzed=make_analyzed_payload(),
        metrics=MetricsPayload(lead_time_avg_days=15, narrative="N"),
        sprint=SprintPayload(velocity_trend="stable", insights="I"),
    )
    html = await ReportGenerator(client).run(agg)
    assert "<!DOCTYPE html>" in html
    assert "MyProject" in html
    assert "Do X" in html
    assert "At-risk items" in html


def test_json_extractor_handles_fences():
    from src.tools.json_utils import extract_json
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('text {"b": 2} more') == {"b": 2}
