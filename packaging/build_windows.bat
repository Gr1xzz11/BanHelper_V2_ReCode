@echo off
setlocal
cd /d "%~dp0\.."
python -m PyInstaller packaging\banhelper.spec --noconfirm --clean
