@echo off
chcp 65001 >nul
rem 카드 리더만 따로 시험한다 (키오스크 없이). 카드를 대면 읽었는지 · 못 읽은 이유를 한국어로 보여 준다.
rem 키오스크가 켜져 있으면 먼저 끈다 (같은 포트를 같이 못 씀).
setlocal
cd /d "%~dp0"
title COFFEE ^& SPOON - 카드 리더 시험
set "PY=%LOCALAPPDATA%\CoffeeSpoonKiosk\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
"%PY%" tools\check_card_reader.py %*
pause
