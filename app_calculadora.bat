@echo off
REM Launcher pra Calculadora Interativa de Backtest (Streamlit).
REM Requer: pip install -e ".[ui]"

cd /d "%~dp0"
streamlit run app_calculadora.py
exit /b %ERRORLEVEL%
