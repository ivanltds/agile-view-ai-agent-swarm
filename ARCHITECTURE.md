# Architecture

This document describes the internal design of the Azure Boards Agent Swarm: how agents are structured, how they communicate, and how the system handles errors and scaling.

---

## Overview

The system follows a **coordinator-worker pattern** implemented as an async Python application powered by the Claude API. A single Orchestrator agent manages a pool of specialized worker agents, each responsible for one concern: fetching data, analyzing items, computing metrics, analyzing sprints, or generating the report.

```
User CLI input
     │
     ▼
┌─────────────────────────────────┐
│         Orchestrator Agent      │
│  - Validates credentials        │
│  - Dispatches parallel tasks    │
│  - Aggregates results           │
│  - Handles errors and retries   │
└────────┬────────────────────────┘
         │ asyncio.gather()
    ┌────┴─────────────────────────────┐
    │                                  │
    ▼                                  ▼
Data Fetcher          ┌───────────────────────────┐
    │                 │   Parallel analysis layer  │
    │  raw payload    │                           │
    └────────────────▶│  Work Item Analyzer       │
                      │  Metrics Calculator       │
                      │  Sprint Analyzer          │
                      └──────────┬────────────────┘
                                 │ enriched payload
                                 ▼
                         Report Generator
                                 │
                                 ▼
                       report_YYYYMMDD.html
```

---

## Execution flow

### Phase 1 — Validation

The Orchestrator calls the Azure DevOps API with a lightweight request to verify that the PAT is valid and that the project and team names exist. If this fails, the process stops immediately with a descriptive error.

Endpoint used: `GET https://dev.azure.com/{org}/_apis/projects/{project}`

### Phase 2 — Data collection

The Data Fetcher agent runs a WIQL query to retrieve all work items for the configured time window. It handles:

- Pagination (Azure API returns max 200 items per request)
- Parallel batch resolution (fetching item details in batches of 50)
- Iteration (sprint) metadata
- Team member list

The Data Fetcher returns a normalized `RawPayload` object consumed by all analysis agents.

### Phase 3 — Parallel analysis

Three agents run concurrently via `asyncio.gather`:

- **Work Item Analyzer**: maps items to canonical types and states, computes state transition timestamps, and flags blocked/unestimated items.
- **Metrics Calculator**: computes Lead Time, Cycle Time, Throughput, Bug Rate, and reopen rate from the analyzed items.
- **Sprint Analyzer**: computes velocity per sprint and burndown data for the current sprint.

### Phase 4 — Report generation

The Report Generator receives the aggregated payload from all three analysis agents plus the original raw data. It renders the HTML template using Jinja2, embedding the metric data as inline JSON that Chart.js reads to render the visualizations.

The output is a single self-contained `.html` file with no external dependencies (Chart.js is inlined or loaded from CDN with a fallback).

---

## Agent communication

Agents do not call each other directly. All communication goes through the Orchestrator, which passes data as Python dataclasses (defined in `src/models/schemas.py`). This keeps agents stateless and independently testable.

```
Orchestrator
    ├── sends RawPayload ──▶ WorkItemAnalyzer
    │       └── receives AnalyzedPayload
    ├── sends RawPayload ──▶ MetricsCalculator
    │       └── receives MetricsPayload
    ├── sends RawPayload ──▶ SprintAnalyzer
    │       └── receives SprintPayload
    └── sends AggregatedPayload ──▶ ReportGenerator
            └── receives HTML string
```

---

## Claude API usage

Each agent is a function that constructs a prompt, calls `anthropic.messages.create`, and parses the response. The agents use Claude for:

- **Work Item Analyzer**: interpreting ambiguous state names and custom fields that vary by organization
- **Metrics Calculator**: generating narrative context around numeric results (e.g. "Lead time is high relative to team size")
- **Sprint Analyzer**: identifying patterns across sprints (e.g. consistent underestimation)
- **Report Generator**: writing the Recommendations section based on the full aggregated payload

Data fetching and HTML rendering do not use the Claude API — they are deterministic Python code.

### Model

All agents use `claude-sonnet-4-20250514`. Tool use is not required for this swarm; agents receive structured JSON in the prompt and return structured JSON in the response (parsed with a robust extractor that handles markdown fences).

---

## Data models

All schemas are defined in `src/models/schemas.py` using Pydantic v2.

```
RawPayload
├── work_items: list[RawWorkItem]
├── iterations: list[Iteration]
├── team_members: list[TeamMember]
└── metadata: ProjectMetadata

AnalyzedPayload
├── items: list[AnalyzedWorkItem]
├── blocked_items: list[str]          # item IDs
└── unestimated_items: list[str]

MetricsPayload
├── lead_time_avg_days: float
├── lead_time_p85_days: float
├── cycle_time_avg_days: float
├── cycle_time_p85_days: float
├── throughput_per_sprint: list[int]
├── bug_rate_pct: float
└── reopen_rate_pct: float

SprintPayload
├── velocity_per_sprint: list[SprintVelocity]
├── current_burndown: list[BurndownPoint]
└── current_sprint: Iteration

AggregatedPayload
├── raw: RawPayload
├── analyzed: AnalyzedPayload
├── metrics: MetricsPayload
└── sprint: SprintPayload
```

---

## Error handling

| Error type | Behavior |
|---|---|
| Invalid PAT or 401 | Abort immediately, print actionable message |
| Project or team not found (404) | Abort with suggestion to check names |
| Rate limit hit (429) | Exponential backoff, max 3 retries |
| Empty result set | Continue with warning, generate partial report |
| Agent parse failure | Log raw response, skip that section in the report |
| Network timeout | Retry once, then abort with message |

All errors are surfaced to the CLI with plain-language messages. Stack traces are only shown with `--verbose`.

---

## Security considerations

- The PAT is read once, stored in memory, and never written to disk, logs, or the report.
- The preferred input method is the `AZURE_PAT` environment variable — passing secrets as CLI flags leaves them in shell history.
- The Orchestrator validates the PAT scope before any data is fetched. If the PAT lacks `Work Items (Read)`, it fails early with a clear message.
- The generated HTML is fully static — no server calls, no embedded credentials.

---

## Extending the swarm

To add a new agent:

1. Create `src/agents/my_agent.py` implementing the `BaseAgent` interface.
2. Add its input/output schemas to `src/models/schemas.py`.
3. Register it in `src/agents/orchestrator.py` under the parallel analysis phase.
4. Add its output to `AggregatedPayload` and update the report template if needed.

See [AGENTS.md](AGENTS.md) for detailed agent interface documentation and [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution workflow.
