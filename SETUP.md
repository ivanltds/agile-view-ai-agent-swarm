# Setup Guide

Complete installation and configuration guide for the Azure Boards Agent Swarm.

---

## Prerequisites

| Requirement | Minimum version | How to check |
|---|---|---|
| Python | 3.11 | `python --version` |
| pip | 23.0 | `pip --version` |
| Anthropic API key | — | [console.anthropic.com](https://console.anthropic.com) |
| Azure DevOps access | — | Your organization URL |

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/your-org/azure-boards-swarm.git
cd azure-boards-swarm
```

---

## Step 2 — Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows
```

---

## Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Core dependencies

| Package | Version | Purpose |
|---|---|---|
| `anthropic` | >=0.40.0 | Claude API client |
| `httpx` | >=0.27.0 | Async HTTP client for Azure API |
| `pydantic` | >=2.0 | Data validation and schemas |
| `pydantic-settings` | >=2.0 | Environment variable loading |
| `jinja2` | >=3.1 | HTML report templating |
| `click` | >=8.1 | CLI interface |
| `python-dotenv` | >=1.0 | `.env` file support |

---

## Step 4 — Create an Azure Personal Access Token

The swarm needs a PAT with read-only access to your Azure DevOps project.

1. Go to `https://dev.azure.com/{your-org}` and sign in.
2. Click your profile icon (top right) → **Personal access tokens**.
3. Click **New Token**.
4. Set a name (e.g., `boards-swarm-readonly`).
5. Set expiration as appropriate for your use case.
6. Under **Scopes**, select **Custom defined** and enable:
   - **Work Items** → Read
   - **Project and Team** → Read
7. Click **Create** and copy the token immediately — it will not be shown again.

> **Minimum required scopes:** `vso.work` (Work Items Read) and `vso.project` (Project and Team Read).
> Do not grant more permissions than needed.

---

## Step 5 — Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```dotenv
# Required
ANTHROPIC_API_KEY=sk-ant-...
AZURE_ORG=your-organization-name
AZURE_PAT=your-pat-here

# Optional — can also be passed as CLI flags
AZURE_PROJECT=MyProject
AZURE_TEAM=TeamAlpha

# Optional — swarm behavior
SWARM_SPRINTS=5             # number of past sprints to analyze
SWARM_OUTPUT_DIR=./reports  # where to save HTML reports
SWARM_VERBOSE=false         # show agent activity logs
```

> **Security note:** Never commit `.env` to version control. It is already in `.gitignore`.
> Prefer environment variables over CLI flags for secrets, as CLI flags appear in shell history.

---

## Step 6 — Verify the setup

Run the built-in validation command to confirm credentials are working:

```bash
python src/main.py --validate \
  --org "your-org" \
  --project "MyProject" \
  --team "TeamAlpha"
```

Expected output:

```
✓ Anthropic API key valid
✓ Azure DevOps connection successful
✓ Project "MyProject" found
✓ Team "TeamAlpha" found (6 members)
✓ Work items accessible (423 items in range)

Setup complete. Run without --validate to generate the report.
```

---

## Step 7 — Generate your first report

```bash
python src/main.py \
  --org "your-org" \
  --project "MyProject" \
  --team "TeamAlpha"
```

If `AZURE_PAT` is set in your environment, you do not need to pass `--pat`.

The report is saved in the current directory (or `SWARM_OUTPUT_DIR` if configured):

```
report_MyProject_TeamAlpha_20241215_143022.html
```

Open it in any browser — it is fully self-contained.

---

## CLI reference

```
Usage: python src/main.py [OPTIONS]

Options:
  --org TEXT        Azure DevOps organization name  [required]
  --project TEXT    Azure DevOps project name       [required]
  --team TEXT       Team name within the project    [required]
  --pat TEXT        Personal Access Token (prefer AZURE_PAT env var)
  --sprints INT     Number of past sprints to analyze  [default: 5]
  --output PATH     Directory to save the HTML report  [default: .]
  --validate        Validate credentials without generating report
  --verbose         Show detailed agent activity logs
  --help            Show this message and exit
```

---

## Troubleshooting

### 401 Unauthorized

Your PAT is invalid or expired. Generate a new one following Step 4 and update your `.env`.

### 404 — Project not found

The project name is case-sensitive. Verify the exact name in your Azure DevOps URL:
`https://dev.azure.com/{org}/{ProjectName}`

### 404 — Team not found

Navigate to **Project Settings → Teams** in Azure DevOps and copy the exact team name.

### Empty report — no work items found

The WIQL query searches the last 90 days by default. If your team hasn't been active in that window, try adjusting the date range in `src/agents/data_fetcher.py` or contact your Azure DevOps administrator to verify area path permissions.

### Rate limit errors (429)

The swarm includes automatic exponential backoff. If errors persist, reduce concurrency by setting `SWARM_BATCH_SIZE=25` in your `.env` (default is 50 items per batch).

### Anthropic API errors

Verify your `ANTHROPIC_API_KEY` at [console.anthropic.com](https://console.anthropic.com). Confirm the key has access to `claude-sonnet-4-20250514`.

### Report opens but charts are blank

The report loads Chart.js from CDN. Open the file while connected to the internet, or see [CONTRIBUTING.md](CONTRIBUTING.md) for instructions on bundling Chart.js inline for offline use.

---

## Running in CI/CD

To generate reports automatically (e.g., at the end of each sprint):

```yaml
# .github/workflows/sprint-report.yml
name: Sprint report

on:
  schedule:
    - cron: '0 9 * * 1'   # Every Monday at 9am UTC

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python src/main.py --org "$AZURE_ORG" --project "$AZURE_PROJECT" --team "$AZURE_TEAM" --output ./reports
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          AZURE_PAT: ${{ secrets.AZURE_PAT }}
          AZURE_ORG: your-organization
          AZURE_PROJECT: MyProject
          AZURE_TEAM: TeamAlpha
      - uses: actions/upload-artifact@v4
        with:
          name: sprint-report
          path: reports/*.html
```

> Store `ANTHROPIC_API_KEY` and `AZURE_PAT` as GitHub Actions secrets, never as plain text in the workflow file.
