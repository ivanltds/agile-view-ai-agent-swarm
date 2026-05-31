# Agents

This document describes each agent in the swarm: its responsibility, inputs, outputs, Claude API usage, and implementation notes.

---

## Base interface

All agents implement a common async interface:

```python
class BaseAgent:
    name: str
    description: str

    async def run(self, payload: Any) -> Any:
        ...
```

Agents are stateless. They receive a payload, do their work, and return a result. The Orchestrator owns all state.

---

## Orchestrator Agent

**File:** `src/agents/orchestrator.py`

### Responsibility

The Orchestrator is the entry point and coordinator of the swarm. It does not analyze data itself — it validates inputs, sequences the execution phases, and aggregates results.

### Does not use Claude API

The Orchestrator is pure Python logic. It calls the Azure API directly for credential validation and delegates all LLM work to the specialist agents.

### Execution steps

1. Validate that `project`, `team`, and `pat` are non-empty.
2. Call `GET /projects/{project}` to verify the PAT and project exist.
3. Call `GET /teams/{team}` to verify the team exists within the project.
4. Instantiate and run the Data Fetcher.
5. Run Work Item Analyzer, Metrics Calculator, and Sprint Analyzer concurrently with `asyncio.gather`.
6. Pass the aggregated payload to the Report Generator.
7. Write the HTML output to disk.

### Error policy

Any unrecoverable error in steps 1–4 raises `OrchestratorError` and halts the process. Errors in steps 5–6 are caught per-agent: if an analysis agent fails, the Orchestrator logs a warning and marks that section as unavailable in the report rather than aborting entirely.

---

## Data Fetcher Agent

**File:** `src/agents/data_fetcher.py`

### Responsibility

Retrieves all raw data from the Azure DevOps REST API. This is the only agent that makes external HTTP calls (except for the Orchestrator's validation step).

### Does not use Claude API

All logic here is deterministic: HTTP calls, pagination, and data normalization.

### Inputs

```python
@dataclass
class FetcherInput:
    org: str
    project: str
    team: str
    pat: str
    sprints_back: int = 5
```

### Outputs

```python
RawPayload  # see ARCHITECTURE.md for schema
```

### API endpoints used

| Endpoint | Purpose |
|---|---|
| `GET /_apis/wit/wiql` | WIQL query to get work item IDs |
| `POST /_apis/wit/workitemsbatch` | Batch-fetch work item details |
| `GET /_apis/work/teamsettings/iterations` | Get sprint list |
| `GET /_apis/work/iterations/{id}/workitems` | Items per sprint |
| `GET /_apis/projects/{project}/teams/{team}/members` | Team members |

### Pagination strategy

WIQL returns a maximum of 200 IDs per call. The agent pages automatically and fetches item details in batches of 50 using `workitemsbatch`. All batches run concurrently.

### WIQL query

```wiql
SELECT [System.Id]
FROM WorkItems
WHERE [System.TeamProject] = @project
  AND [System.AreaPath] UNDER @project
  AND [System.ChangedDate] >= @today - 90
ORDER BY [System.ChangedDate] DESC
```

The 90-day window is configurable via the `--sprints` flag (number of sprints × average sprint length).

---

## Work Item Analyzer Agent

**File:** `src/agents/work_item_analyzer.py`

### Responsibility

Transforms raw work item data into a structured, classified representation. Handles the messiness of real Azure Boards data: custom state names, missing fields, inconsistent types.

### Uses Claude API

Claude resolves ambiguity in custom state mappings. For example, an organization might use "Doing" instead of "Active" or "Ready for QA" instead of "Resolved". The agent sends a sample of state names to Claude and receives a canonical mapping.

### Prompt structure

```
System: You are a work item state classifier for Azure DevOps.
        Map the given custom state names to canonical states:
        New, Active, Resolved, Closed, Removed.
        Respond only with a JSON object: {"custom_state": "canonical_state", ...}

User:   These are the state names found in this project:
        ["Doing", "Ready for QA", "In Review", "Done", "Blocked", ...]
```

### Inputs

```python
RawPayload
```

### Outputs

```python
@dataclass
class AnalyzedPayload:
    items: list[AnalyzedWorkItem]
    blocked_items: list[str]       # item IDs
    unestimated_items: list[str]   # item IDs
    state_map: dict[str, str]      # custom → canonical
```

### Classification logic

- **Type**: read from `System.WorkItemType`. Normalized to: `Epic`, `Feature`, `UserStory`, `Task`, `Bug`, `Other`.
- **State**: mapped via Claude-resolved `state_map`.
- **Blocked**: items with a `Blocked` tag or in a "Blocked" state variant.
- **Unestimated**: items of type UserStory or Task with `null` or `0` story points.
- **State timestamps**: extracted from the work item's revision history to compute when each item entered `Active` and `Closed` states.

---

## Metrics Calculator Agent

**File:** `src/agents/metrics_calculator.py`

### Responsibility

Computes all efficiency KPIs from the analyzed work item data.

### Uses Claude API

After computing the numeric metrics, the agent sends the full metrics summary to Claude and asks for a short narrative paragraph interpreting the numbers in context (team size, sprint length, work item volume). This paragraph appears in the report's Executive Summary.

### Inputs

```python
AnalyzedPayload
RawPayload  # for team size and sprint length
```

### Outputs

```python
@dataclass
class MetricsPayload:
    lead_time_avg_days: float
    lead_time_p85_days: float
    cycle_time_avg_days: float
    cycle_time_p85_days: float
    throughput_per_sprint: list[int]
    throughput_avg: float
    bug_rate_pct: float
    reopen_rate_pct: float
    unestimated_pct: float
    story_points_delivered: list[float]   # per sprint
    story_points_planned: list[float]     # per sprint
    narrative: str                         # Claude-generated
```

### Metric definitions

**Lead Time**
Time from item creation (`System.CreatedDate`) to closure (`System.ClosedDate`). Computed only for items in `Closed` state. Reported as average and 85th percentile.

**Cycle Time**
Time from first `Active` state entry to closure. Uses state transition timestamps extracted by the Work Item Analyzer. Reported as average and 85th percentile.

**Throughput**
Count of items moved to `Closed` within each sprint's date range. Computed per sprint and averaged.

**Bug Rate**
`count(type == Bug AND state != Removed) / count(all items) × 100`

**Reopen Rate**
Items that transitioned from `Closed` back to any active state, divided by total closed items.

**Story Points Planned vs Delivered**
Planned: sum of story points for items added to a sprint before its start date.
Delivered: sum of story points for items closed within the sprint's date range.

---

## Sprint Analyzer Agent

**File:** `src/agents/sprint_analyzer.py`

### Responsibility

Produces sprint-level views: velocity history and the current sprint burndown.

### Uses Claude API

The agent sends velocity data across the last N sprints to Claude and asks it to identify patterns — for example, consistently underdelivering in the third sprint of a quarter, or velocity drops correlating with team size changes. The output is a short insight block in the report.

### Inputs

```python
RawPayload   # iterations and per-sprint items
AnalyzedPayload
```

### Outputs

```python
@dataclass
class SprintVelocity:
    sprint_name: str
    sprint_start: date
    sprint_end: date
    planned_points: float
    delivered_points: float
    item_count: int

@dataclass
class BurndownPoint:
    date: date
    remaining_points: float
    ideal_remaining: float

@dataclass
class SprintPayload:
    velocity_per_sprint: list[SprintVelocity]
    current_burndown: list[BurndownPoint]
    current_sprint: Iteration
    velocity_avg: float
    velocity_trend: str    # "improving", "stable", "declining"
    insights: str          # Claude-generated
```

### Burndown calculation

For the current sprint:
- **Total planned points**: sum of story points for all items in the sprint at start date.
- **Remaining points per day**: total planned minus sum of story points for items closed on or before each calendar day.
- **Ideal line**: linear from total planned on day 0 to 0 on the last day of the sprint.

Weekends are included in the chart but flagged for visual differentiation in the template.

---

## Report Generator Agent

**File:** `src/agents/report_generator.py`

### Responsibility

Assembles the final HTML report from all analyzed data. Produces a single self-contained `.html` file.

### Uses Claude API

The Report Generator asks Claude to write the **Recommendations** section: three to five concrete, actionable recommendations based on the full aggregated payload. The prompt includes all computed metrics, sprint insights, and the metrics narrative.

### Inputs

```python
AggregatedPayload  # contains raw + analyzed + metrics + sprint
```

### Outputs

```python
str  # complete HTML document
```

### Rendering approach

The agent uses Jinja2 to render `templates/report.html.j2`. Metric data is passed to the template as a Python dict, which is serialized to inline JSON and read by Chart.js for rendering charts.

```html
<!-- Inside the template -->
<script>
const velocityData = {{ velocity_data | tojson }};
const burndownData = {{ burndown_data | tojson }};
</script>
```

Chart.js is loaded from CDN with an inline fallback warning if the CDN is unreachable (useful for offline usage).

### Report structure

| Section | Source |
|---|---|
| Header | ProjectMetadata |
| KPI cards | MetricsPayload |
| Velocity chart | SprintPayload.velocity_per_sprint |
| Burndown chart | SprintPayload.current_burndown |
| Work item distribution | AnalyzedPayload.items |
| Team breakdown | RawPayload.team_members + AnalyzedPayload.items |
| At-risk items table | AnalyzedPayload.blocked_items + unestimated_items |
| Recommendations | Claude-generated via Report Generator |

### Output file naming

```
report_{project}_{team}_{YYYYMMDD}_{HHMMSS}.html
```

Spaces in project and team names are replaced with underscores.
