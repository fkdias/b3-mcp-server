@echo off
REM Atualizacao semanal dos datasets offline do B3 MCP Server.
REM Rodado via Windows Task Scheduler (ver AGENDAMENTO.md).
REM %~dp0 resolve pro diretorio deste .bat, evitando hardcode de path.

cd /d "%~dp0"
python atualizar_datasets.py
exit /b %ERRORLEVEL%
