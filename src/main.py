"""CLI entry point for the Azure Boards Agent Swarm."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from anthropic import AsyncAnthropic

# Allow `python src/main.py` to resolve the `src` package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.orchestrator import Orchestrator, OrchestratorError  # noqa: E402
from src.config import load_settings  # noqa: E402
from src.tools.azure_api import AzureAPIError, AzureClient  # noqa: E402


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


async def _validate(org, project, team, pat, anthropic_key) -> int:
    click.echo("Validating credentials...")
    if anthropic_key:
        click.echo("✓ Anthropic API key present")
    else:
        click.echo("✗ Anthropic API key missing", err=True)
    async with AzureClient(org, pat) as azure:
        orch = Orchestrator(AsyncAnthropic(api_key=anthropic_key or "x"), azure)
        try:
            info = await orch.validate(org, project, team)
        except OrchestratorError as exc:
            click.echo(f"✗ {exc}", err=True)
            return 1
    click.echo("✓ Azure DevOps connection successful")
    click.echo(f"✓ Project \"{info['project']}\" found")
    click.echo(f"✓ Team \"{team}\" found ({info['member_count']} members)")
    click.echo("\nSetup complete. Run without --validate to generate the report.")
    return 0


async def _generate(
    org, project, team, pat, anthropic_key, sprints, output, batch_size, verbose
) -> int:
    async with AzureClient(org, pat) as azure:
        orch = Orchestrator(AsyncAnthropic(api_key=anthropic_key), azure)
        try:
            agg = await orch.run(org, project, team, pat, sprints, batch_size)
        except OrchestratorError as exc:
            click.echo(f"Error: {exc}", err=True)
            return 1
        html = await orch.generate_report(agg)

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / orch.output_filename(project, team)
    out_path.write_text(html, encoding="utf-8")
    if agg.unavailable_sections:
        click.echo(f"Note: some sections unavailable: {', '.join(agg.unavailable_sections)}")
    click.echo(f"Report written to {out_path}")
    return 0


@click.command()
@click.option("--org", help="Azure DevOps organization name")
@click.option("--project", help="Azure DevOps project name")
@click.option("--team", help="Team name within the project")
@click.option("--pat", help="Personal Access Token (prefer AZURE_PAT env var)")
@click.option("--sprints", type=int, help="Number of past sprints to analyze")
@click.option("--output", type=click.Path(), help="Directory to save the HTML report")
@click.option("--validate", "validate_only", is_flag=True, help="Validate credentials only")
@click.option("--verbose", is_flag=True, help="Show detailed agent activity logs")
def main(org, project, team, pat, sprints, output, validate_only, verbose):
    """Generate an Azure Boards efficiency report using an AI agent swarm."""
    settings = load_settings()
    org = org or settings.azure_org
    project = project or settings.azure_project
    team = team or settings.azure_team
    pat = pat or settings.azure_pat
    sprints = sprints or settings.swarm_sprints
    output = output or settings.swarm_output_dir
    verbose = verbose or settings.swarm_verbose
    batch_size = settings.swarm_batch_size
    anthropic_key = settings.anthropic_api_key

    _setup_logging(verbose)

    missing = [n for n, v in (("org", org), ("project", project), ("team", team), ("pat", pat)) if not v]
    if missing:
        raise click.UsageError(f"Missing required values: {', '.join(missing)} (set via flag or env)")

    try:
        if validate_only:
            code = asyncio.run(_validate(org, project, team, pat, anthropic_key))
        else:
            if not anthropic_key:
                raise click.UsageError("ANTHROPIC_API_KEY is required to generate a report")
            code = asyncio.run(
                _generate(org, project, team, pat, anthropic_key, sprints, output, batch_size, verbose)
            )
    except AzureAPIError as exc:
        click.echo(f"Azure error: {exc}", err=True)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
