@echo off
setlocal
title Azure Boards - Gerar Relatorio
cd /d "%~dp0"

echo ============================================================
echo   Azure Boards - Gerador de Relatorio
echo ============================================================
echo.

REM 1) Verifica se o Python esta instalado
where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python nao foi encontrado no seu computador.
  echo     Instale em https://www.python.org/downloads/
  echo     IMPORTANTE: marque a opcao "Add Python to PATH" durante a instalacao.
  echo.
  pause
  exit /b 1
)

REM 2) Cria o ambiente e instala as dependencias na primeira vez
if not exist ".venv\" (
  echo Preparando o programa pela primeira vez. Isso pode levar 1-2 minutos...
  python -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

echo.
REM 3) Roda o assistente guiado
python src\main.py --wizard

echo.
echo ============================================================
echo   Concluido. Voce pode fechar esta janela.
echo ============================================================
pause
