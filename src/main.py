"""CLI entry point for the Azure Boards Agent Swarm."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click

# Allow `python src/main.py` to resolve the `src` package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.orchestrator import Orchestrator, OrchestratorError  # noqa: E402
from src.config import load_settings  # noqa: E402
from src.tools.ai_client import AIClient, _detect_provider  # noqa: E402
from src.tools.azure_api import AzureAPIError, AzureClient  # noqa: E402

_PROVIDER_HINTS = {
    "anthropic": "começa com sk-ant-  →  console.anthropic.com",
    "openai":    "começa com sk-       →  platform.openai.com",
    "deepseek":  "qualquer valor       →  platform.deepseek.com",
    "gemini":    "começa com AIza      →  aistudio.google.com",
}


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _make_ai_client(ai_key: str, provider: str | None, model: str | None) -> AIClient:
    return AIClient(api_key=ai_key, provider=provider, model=model)


async def _validate(org, project, team, pat, ai_client) -> int:
    click.echo("Validando credenciais...")
    click.echo(f"✓ Chave de IA presente (provedor: {ai_client.provider})")
    async with AzureClient(org, pat) as azure:
        orch = Orchestrator(ai_client, azure)
        try:
            info = await orch.validate(org, project, team)
        except OrchestratorError as exc:
            click.echo(f"✗ {exc}", err=True)
            return 1
    click.echo("✓ Conexão com Azure DevOps bem-sucedida")
    click.echo(f"✓ Projeto \"{info['project']}\" encontrado")
    click.echo(f"✓ Time \"{team}\" encontrado ({info['member_count']} membros)")
    click.echo("\nTudo certo. Execute sem --validate para gerar o relatório.")
    return 0


async def _generate(
    org, project, team, pat, ai_client, sprints, output, batch_size, verbose
) -> int:
    async with AzureClient(org, pat) as azure:
        orch = Orchestrator(ai_client, azure)
        try:
            agg = await orch.run(org, project, team, pat, sprints, batch_size)
        except OrchestratorError as exc:
            click.echo(f"Erro: {exc}", err=True)
            return 1
        html = await orch.generate_report(agg)

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / orch.output_filename(project, team)
    out_path.write_text(html, encoding="utf-8")
    if agg.unavailable_sections:
        click.echo(f"Aviso: seções indisponíveis: {', '.join(agg.unavailable_sections)}")
    click.echo(f"Relatório salvo em {out_path}")
    try:
        import webbrowser
        webbrowser.open(out_path.resolve().as_uri())
        click.echo("Abrindo o relatório no navegador...")
    except Exception:  # noqa: BLE001
        pass
    return 0


def _save_env(values: dict[str, str]) -> None:
    env_path = Path(".env")
    existing: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v
    existing.update({k: v for k, v in values.items() if v})
    lines = ["# Salvo pelo assistente. Mantenha este arquivo privado."]
    lines += [f"{k}={v}" for k, v in existing.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_wizard(settings) -> dict:
    click.echo("=" * 60)
    click.echo("  Azure Boards Report — Assistente de Configuração")
    click.echo("=" * 60)
    click.echo("Responda algumas perguntas e o relatório será gerado.\n")

    existing_key = settings.resolve_ai_key()
    if existing_key:
        ai_key = existing_key
        provider = settings.ai_provider or _detect_provider(ai_key)
        click.echo(f"1) Chave de IA já salva (provedor detectado: {provider})")
    else:
        click.echo("1) Chave de IA — escolha uma das opções abaixo:")
        for p, hint in _PROVIDER_HINTS.items():
            click.echo(f"   • {p:10s}  {hint}")
        ai_key = click.prompt("   Cole sua chave aqui", hide_input=True)
        provider = settings.ai_provider or _detect_provider(ai_key)
        click.echo(f"   → Provedor detectado: {provider}")

    org = settings.azure_org or click.prompt("2) Nome da organização no Azure DevOps")
    project = settings.azure_project or click.prompt("3) Nome do projeto")
    team = settings.azure_team or click.prompt("4) Nome do time")
    pat = settings.azure_pat or click.prompt("5) Token pessoal do Azure (PAT)", hide_input=True)
    sprints = click.prompt(
        "6) Quantos sprints passados analisar", default=settings.swarm_sprints, type=int
    )

    if click.confirm("\nSalvar para não precisar digitar da próxima vez?", default=True):
        key_field = f"{provider.upper()}_API_KEY"
        _save_env({
            key_field: ai_key,
            "AI_PROVIDER": provider,
            "AZURE_ORG": org,
            "AZURE_PAT": pat,
            "AZURE_PROJECT": project,
            "AZURE_TEAM": team,
            "SWARM_SPRINTS": str(sprints),
        })
        click.echo("Salvo em .env (mantenha este arquivo privado).")

    return {"org": org, "project": project, "team": team,
            "pat": pat, "sprints": sprints, "ai_key": ai_key, "provider": provider}


@click.command()
@click.option("--org", help="Nome da organização no Azure DevOps")
@click.option("--project", help="Nome do projeto no Azure DevOps")
@click.option("--team", help="Nome do time dentro do projeto")
@click.option("--pat", help="Personal Access Token (prefira a variável AZURE_PAT)")
@click.option("--sprints", type=int, help="Número de sprints passados a analisar")
@click.option("--output", type=click.Path(), help="Diretório para salvar o relatório HTML")
@click.option("--validate", "validate_only", is_flag=True, help="Apenas valida credenciais")
@click.option("--wizard", "wizard", is_flag=True, help="Executa o assistente interativo")
@click.option("--verbose", is_flag=True, help="Exibe logs detalhados dos agentes")
@click.option("--provider", "ai_provider", help="Provedor de IA: anthropic | openai | deepseek | gemini")
@click.option("--model", "ai_model", help="Modelo específico (sobrescreve o padrão do provedor)")
def main(org, project, team, pat, sprints, output, validate_only, wizard, verbose, ai_provider, ai_model):
    """Gera um relatório de eficiência do Azure Boards usando um swarm de agentes de IA."""
    settings = load_settings()
    org = org or settings.azure_org
    project = project or settings.azure_project
    team = team or settings.azure_team
    pat = pat or settings.azure_pat
    sprints = sprints or settings.swarm_sprints
    output = output or settings.swarm_output_dir
    verbose = verbose or settings.swarm_verbose
    batch_size = settings.swarm_batch_size
    ai_provider = ai_provider or settings.ai_provider
    ai_model = ai_model or settings.ai_model
    ai_key = settings.resolve_ai_key()

    _setup_logging(verbose)

    missing = [n for n, v in (("org", org), ("project", project), ("team", team), ("pat", pat)) if not v]

    if wizard or (missing and not validate_only):
        answers = _run_wizard(settings)
        org, project, team = answers["org"], answers["project"], answers["team"]
        pat, sprints = answers["pat"], answers["sprints"]
        ai_key = answers["ai_key"]
        ai_provider = answers["provider"]
        missing = [n for n, v in (("org", org), ("project", project), ("team", team), ("pat", pat)) if not v]

    if missing:
        raise click.UsageError(f"Valores ausentes: {', '.join(missing)} (defina via flag ou variável de ambiente)")

    if not ai_key:
        raise click.UsageError(
            "Chave de IA não encontrada. Defina ANTHROPIC_API_KEY, OPENAI_API_KEY, "
            "DEEPSEEK_API_KEY ou GEMINI_API_KEY."
        )

    ai_client = _make_ai_client(ai_key, ai_provider, ai_model)

    try:
        if validate_only:
            code = asyncio.run(_validate(org, project, team, pat, ai_client))
        else:
            code = asyncio.run(
                _generate(org, project, team, pat, ai_client, sprints, output, batch_size, verbose)
            )
    except AzureAPIError as exc:
        click.echo(f"Erro Azure: {exc}", err=True)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
