# Azure Boards Agent Swarm

> Multi-agent system that queries Azure DevOps Boards and generates a complete HTML efficiency report using AI-powered analysis.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Claude](https://img.shields.io/badge/powered%20by-Claude%20API-purple.svg)

---

## What it does

You provide three inputs. The swarm does the rest.

```
Project name  ──┐
Team name     ──┼──▶  Agent Swarm  ──▶  report_20241215_143022.html
PAT key       ──┘
```

The generated HTML report includes:

- Executive summary with main KPIs (Lead Time, Cycle Time, Throughput, Velocity)
- Velocity chart across recent sprints
- Current sprint burndown chart
- Work item distribution by type and status
- Per-member delivery breakdown
- At-risk items (blocked, missing estimates, overdue)
- AI-generated recommendations based on the data

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/your-org/azure-boards-swarm.git
cd azure-boards-swarm
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key and optionally your Azure PAT
```

### 3. Run

```bash
python src/main.py \
  --project "MyProject" \
  --team "TeamAlpha" \
  --pat "your-azure-pat-here"
```

Or using environment variables (recommended):

```bash
export AZURE_PAT="your-azure-pat-here"
python src/main.py --project "MyProject" --team "TeamAlpha"
```

The report is saved as `report_YYYYMMDD_HHMMSS.html` in the current directory.

---

## Configuration options

| Flag | Environment variable | Default | Description |
|---|---|---|---|
| `--project` | `AZURE_PROJECT` | required | Azure DevOps project name |
| `--team` | `AZURE_TEAM` | required | Team name within the project |
| `--pat` | `AZURE_PAT` | required | Personal Access Token |
| `--org` | `AZURE_ORG` | required | Azure DevOps organization name |
| `--sprints` | `SWARM_SPRINTS` | `5` | Number of past sprints to analyze |
| `--output` | `SWARM_OUTPUT_DIR` | `.` | Directory to save the HTML report |
| `--verbose` | — | `false` | Show agent activity logs |

---

## Report sections

| Section | Description |
|---|---|
| Header | Project, team, generation date, analysis period |
| Executive summary | KPI cards: Lead Time, Cycle Time, Throughput, Bug Rate |
| Velocity chart | Story points delivered per sprint (last N sprints) |
| Burndown | Planned vs actual for the current sprint |
| Work item distribution | By type (Epic, Feature, Story, Task, Bug) and by state |
| Team breakdown | Items and story points per member |
| At-risk items | Blocked, no estimate, past due date |
| Recommendations | LLM-generated insights based on the metrics |

---

## Project structure

```
azure-boards-swarm/
├── src/
│   ├── agents/
│   │   ├── orchestrator.py       # Coordinates the swarm
│   │   ├── data_fetcher.py       # Azure DevOps API calls
│   │   ├── work_item_analyzer.py # Classifies and maps work items
│   │   ├── metrics_calculator.py # Computes all KPIs
│   │   ├── sprint_analyzer.py    # Burndown and velocity
│   │   └── report_generator.py  # Builds the HTML output
│   ├── tools/
│   │   ├── azure_api.py          # HTTP client wrapper
│   │   └── html_builder.py       # Jinja2 + Chart.js rendering
│   ├── models/
│   │   └── schemas.py            # Pydantic data models
│   └── main.py                   # CLI entry point
├── templates/
│   └── report.html.j2            # HTML report template
├── examples/
│   └── sample_report.html        # Example output
├── .env.example
├── requirements.txt
├── ARCHITECTURE.md
├── AGENTS.md
├── SETUP.md
└── CONTRIBUTING.md
```

---

## Documentation

- [Architecture](ARCHITECTURE.md) — how the swarm works internally
- [Agents](AGENTS.md) — each agent's role, inputs, and outputs
- [Setup](SETUP.md) — detailed installation and configuration guide
- [Contributing](CONTRIBUTING.md) — how to add agents or extend the report

---

## Requirements

- Python 3.11+
- Anthropic API key with access to Claude Sonnet
- Azure DevOps PAT with scopes: `Work Items (Read)`, `Project and Team (Read)`

---

## License

MIT — see [LICENSE](LICENSE) for details.
