@echo off
title Code Analyser Server
echo Starting Code Analyser...
cd /d "%~dp0code-analyser--main\code analyser"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" app.py
) else (
    python app.py
)
pause
