@echo off
cd /d "%~dp0"
python push_github.py
if errorlevel 1 (
    echo An error occurred.
    pause
)
