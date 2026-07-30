@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  py -3 -m venv "%ROOT%.venv"
  "%PYTHON%" -m pip install -r "%ROOT%requirements.txt"
)
"%PYTHON%" "%ROOT%run.py"
