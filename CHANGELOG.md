# Changelog

All notable changes to this project will be documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added

- **`COMECE-AQUI.md`** — Guia de onboarding em português para usuários não-técnicos.
  - Instruções passo a passo para instalar o Python e gerar o relatório sem precisar saber programar.
  - Tabela de pré-requisitos com links e localização de cada credencial necessária.
  - Guia de criação do Personal Access Token (PAT) no Azure DevOps com escopos mínimos requeridos.
  - Tabela de troubleshooting com os erros mais comuns e ações corretivas.
  - Referência ao `TESTAR-CONEXAO.bat` para validação rápida do acesso.

---

## [1.0.0] — 2026-05-31

### Added

- Implementação inicial do Azure Boards Agent Swarm.
- Agentes: `orchestrator`, `data_fetcher`, `sprint_analyzer`, `work_item_analyzer`, `metrics_calculator`, `report_generator`.
- Templates HTML com gráficos Chart.js para o relatório de eficiência do time.
- Scripts de automação: `GERAR-RELATORIO.bat`, `TESTAR-CONEXAO.bat`.
- Documentação técnica: `ARCHITECTURE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SETUP.md`.
- Suite de testes com pytest cobrindo os principais agentes.
