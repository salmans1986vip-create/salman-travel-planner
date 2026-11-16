@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
echo Installing requirements...
python -m pip install -q -r requirements.txt
echo Starting app at http://localhost:8501
python -m streamlit run app.py
pause
