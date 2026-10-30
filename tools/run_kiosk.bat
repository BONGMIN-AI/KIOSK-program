@echo off
rem COFFEE & SPOON KIOSK launcher with auto-restart.
rem - Runs the GUI full screen from the venv made by 1_처음설치.bat (%LOCALAPPDATA%\CoffeeSpoonKiosk\venv),
rem   or from this project's .venv if that one does not exist.
rem - If the program stops unexpectedly (exit code not 0), it starts again after 3 seconds.
rem - If staff ends it normally (KIOSK exit button or Ctrl+Shift+Q, exit code 0), it stays closed.
rem - To start automatically when Windows boots: press Win+R, type  shell:startup , and put a
rem   shortcut to this file in that folder (see docs/KIOSK_CRASH_SAFETY.md).
rem Add  --demo  after the file name to run with in-memory sample data, e.g.  run_kiosk.bat --demo

chcp 65001 >nul
cd /d "%~dp0.."
if not exist logs mkdir logs
set "PYTHON=%LOCALAPPDATA%\CoffeeSpoonKiosk\venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set PYTHON=python

:start
"%PYTHON%" -m gui.main --fullscreen %*
if %errorlevel%==0 goto end
echo [%date% %time%] KIOSK stopped with code %errorlevel%. Restarting in 3 seconds...>> logs\restarts.log 2>nul
timeout /t 3 /nobreak >nul
goto start

:end
