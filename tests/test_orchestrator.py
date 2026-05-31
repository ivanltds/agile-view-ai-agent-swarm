import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.orchestrator import Orchestrator, OrchestratorError


@pytest.mark.asyncio
async def test_validate_rejects_empty():
    orch = Orchestrator(MagicMock(), MagicMock())
    with pytest.raises(OrchestratorError):
        await orch.validate("", "p", "t")


@pytest.mark.asyncio
async def test_validate_success():
    azure = MagicMock()
    azure.get = AsyncMock(side_effect=[
        {"name": "MyProject"},
        {"value": [{"identity": {"id": "1", "displayName": "Alice"}}]},
    ])
    orch = Orchestrator(MagicMock(), azure)
    info = await orch.validate("acme", "MyProject", "TeamAlpha")
    assert info["project"] == "MyProject"
    assert info["member_count"] == 1


def test_output_filename_sanitizes_spaces():
    name = Orchestrator.output_filename("My Project", "Team Alpha")
    assert name.startswith("report_My_Project_Team_Alpha_")
    assert name.endswith(".html")
