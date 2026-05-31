import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.sprint_analyzer import SprintAnalyzer
from tests.fixtures import make_raw_payload, make_analyzed_payload


@pytest.mark.asyncio
async def test_velocity_and_burndown():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="insight")]
    ))
    agent = SprintAnalyzer(client)
    s = await agent.run(make_raw_payload(), make_analyzed_payload())

    assert len(s.velocity_per_sprint) == 1
    v = s.velocity_per_sprint[0]
    assert v.planned_points == 8.0               # 5 + 3 (item 3 has none)
    assert v.delivered_points == 5.0             # item 1 closed in sprint
    assert s.current_sprint is not None
    assert s.insights == "insight"
