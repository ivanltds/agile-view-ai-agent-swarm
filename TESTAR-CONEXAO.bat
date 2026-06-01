@echo off
setlocal
title Azure Boards - Testar Conexao
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python nao encontrado. Instale em https://www.python.org/downloads/
  pause & exit /b 1
)
if not exist ".venv\" (
  echo Preparando pela primeira vez...
  python -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)
set /p ORG="Organizacao do Azure DevOps: "
set /p PROJ="Nome do projeto: "
set /p TEAM="Nome do time: "
python src\main.py --validate --org "%ORG%" --project "%PROJ%" --team "%TEAM%"
pause
