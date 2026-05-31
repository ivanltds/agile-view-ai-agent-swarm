import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.work_item_analyzer import WorkItemAnalyzer
from tests.fixtures import make_raw_payload


@pytest.mark.asyncio
async def test_classifies_types_states_and_flags():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text='{"Done":"Closed","Active":"Active","Doing":"Active"}')]
    ))
    agent = WorkItemAnalyzer(client)
    result = await agent.run(make_raw_payload())

    by_id = {i.id: i for i in result.items}
    assert by_id[1].type == "UserStory" and by_id[1].state == "Closed"
    assert by_id[2].type == "Bug" and by_id[2].blocked
    assert by_id[3].unestimated
    assert "2" in result.blocked_items and "3" in result.unestimated_items


@pytest.mark.asyncio
async def test_falls_back_when_claude_fails():
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
    agent = WorkItemAnalyzer(client)
    result = await agent.run(make_raw_payload())
    # fallback still maps "Done" -> Closed
    assert result.state_map.get("Done") == "Closed"
