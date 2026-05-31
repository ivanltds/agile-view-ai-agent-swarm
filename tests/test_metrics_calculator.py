import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.metrics_calculator import MetricsCalculator
from tests.fixtures import make_raw_payload, make_analyzed_payload


@pytest.mark.asyncio
async def test_metrics_basic():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="Narrative text")]
    ))
    agent = MetricsCalculator(client)
    m = await agent.run(make_raw_payload(), make_analyzed_payload())

    assert m.lead_time_avg_days == 15.0          # created 20d, closed 5d before NOW
    assert m.cycle_time_avg_days == 10.0
    assert round(m.bug_rate_pct) == 33           # 1 bug of 3 items
    assert m.unestimated_pct > 0
    assert m.narrative == "Narrative text"
