# Contributing

Thank you for your interest in contributing to Azure Boards Agent Swarm. This guide covers how to add new agents, extend the report, fix bugs, and get your changes merged.

---

## Ways to contribute

- Add a new specialist agent (e.g., a Dependency Analyzer or a Risk Scorer)
- Extend the HTML report with new sections or chart types
- Improve the WIQL queries or data normalization logic
- Add support for additional Azure DevOps work item types or custom fields
- Fix bugs or improve error messages
- Improve documentation

---

## Development setup

Follow the [Setup Guide](SETUP.md) to install dependencies. Then install the development extras:

```bash
pip install -r requirements-dev.txt
```

Development dependencies include `pytest`, `pytest-asyncio`, `httpx` mock utilities, and `ruff` for linting.

---

## Project conventions

### Code style

- Formatter: `ruff format` (line length 100)
- Linter: `ruff check` (rules: E, F, I, UP, B, SIM)
- Type hints: required on all public functions
- Docstrings: Google style, required on all agents and public methods

Run both before committing:

```bash
ruff format src/
ruff check src/
```

### Naming

- Agent files: `snake_case.py` in `src/agents/`
- Schema classes: `PascalCase` Pydantic models in `src/models/schemas.py`
- Constants: `UPPER_SNAKE_CASE` in `src/config.py`

### Async

All I/O-bound code must be async. Use `httpx.AsyncClient` for HTTP calls and `asyncio.gather` for concurrent operations. Avoid `time.sleep` — use `asyncio.sleep`.

---

## Adding a new agent

### 1. Define the output schema

Add your output dataclass to `src/models/schemas.py`:

```python
@dataclass
class MyAgentPayload:
    summary: str
    items: list[MyItem]
    insights: str   # Claude-generated narrative
```

If your agent needs Claude to generate narrative content, include a `str` field for it (like `insights` or `narrative`).

### 2. Create the agent file

Create `src/agents/my_agent.py`:

```python
from anthropic import AsyncAnthropic
from src.models.schemas import RawPayload, AnalyzedPayload, MyAgentPayload
from src.agents.base import BaseAgent


class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Does X and Y with the work item data."

    def __init__(self, client: AsyncAnthropic):
        self.client = client

    async def run(self, raw: RawPayload, analyzed: AnalyzedPayload) -> MyAgentPayload:
        # 1. Pure Python computation
        items = self._compute(raw, analyzed)

        # 2. Claude API call for narrative (if needed)
        insights = await self._generate_insights(items)

        return MyAgentPayload(
            summary=f"Found {len(items)} items",
            items=items,
            insights=insights,
        )

    def _compute(self, raw, analyzed):
        # deterministic logic here
        ...

    async def _generate_insights(self, items) -> str:
        prompt = f"""
        Analyze the following data and provide 2-3 concise insights:
        {items}
        Respond with a short paragraph only. No headers or bullet points.
        """
        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
```

### 3. Register the agent in the Orchestrator

In `src/agents/orchestrator.py`, add your agent to the parallel analysis phase:

```python
from src.agents.my_agent import MyAgent

# Inside OrchestratorAgent.run():
my_agent = MyAgent(self.client)

analyzed, metrics, sprint, my_result = await asyncio.gather(
    work_item_analyzer.run(raw_payload),
    metrics_calculator.run(raw_payload),
    sprint_analyzer.run(raw_payload),
    my_agent.run(raw_payload, analyzed_payload),  # add here
)
```

### 4. Add the payload to AggregatedPayload

```python
@dataclass
class AggregatedPayload:
    raw: RawPayload
    analyzed: AnalyzedPayload
    metrics: MetricsPayload
    sprint: SprintPayload
    my_result: MyAgentPayload   # add here
```

### 5. Add a section to the report template

In `templates/report.html.j2`, add a new section:

```html
<!-- My Agent Section -->
<section class="report-section">
  <h2>My New Section</h2>
  <p>{{ my_result.insights }}</p>
  <!-- add charts or tables as needed -->
</section>
```

### 6. Write tests

Add `tests/test_my_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.my_agent import MyAgent
from tests.fixtures import make_raw_payload, make_analyzed_payload


@pytest.mark.asyncio
async def test_my_agent_returns_payload():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="Test insights")]
    ))

    agent = MyAgent(client)
    result = await agent.run(make_raw_payload(), make_analyzed_payload())

    assert result.insights == "Test insights"
    assert isinstance(result.items, list)
```

---

## Extending the HTML report

The report template is `templates/report.html.j2`. It uses Jinja2 and Chart.js.

### Adding a new chart

1. Pass the data from `ReportGenerator` to the template context.
2. In the template, serialize it to inline JSON:

```html
<canvas id="my-chart"></canvas>
<script>
const myData = {{ my_chart_data | tojson }};
new Chart(document.getElementById('my-chart'), {
  type: 'bar',
  data: myData,
  options: { responsive: true }
});
</script>
```

### Bundling Chart.js for offline use

To make the report work without internet access:

```bash
python scripts/bundle_chartjs.py
```

This downloads Chart.js and inlines it into the template. The bundled version is not committed to the repository — run the script locally before generating offline reports.

---

## Running tests

```bash
pytest tests/ -v
```

Tests that make real HTTP calls are marked `@pytest.mark.integration` and skipped by default:

```bash
pytest tests/ -v -m "not integration"    # default (fast)
pytest tests/ -v -m integration          # requires real credentials in .env
```

---

## Submitting a pull request

1. Fork the repository and create a branch: `git checkout -b feat/my-new-agent`
2. Make your changes, following the conventions above.
3. Ensure tests pass: `pytest tests/ -v -m "not integration"`
4. Ensure linting passes: `ruff check src/ && ruff format --check src/`
5. Update relevant documentation (AGENTS.md for new agents, SETUP.md for new config options).
6. Open a pull request with a clear description of what the change does and why.

### PR checklist

- [ ] New agent implements `BaseAgent` interface
- [ ] Output schema added to `src/models/schemas.py`
- [ ] Agent registered in `orchestrator.py`
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] No secrets or credentials in the diff
- [ ] `ruff` checks pass

---

## Reporting issues

Please include:

- Python version (`python --version`)
- Steps to reproduce
- The full error output (with `--verbose` flag if applicable)
- Whether the issue is with credential validation, data fetching, or report generation

Do not include your PAT, API key, or any work item content in bug reports.
