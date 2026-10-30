@echo off
chcp 65001 >nul
rem 시연 모드: 메모리 샘플 데이터로 켠다. 비밀번호·data 폴더·카메라가 없어도 되고 저장되지 않는다.
rem 운영자 로그인은 admin / demo. 전체 화면으로 보려면 명령창에서  2_시연모드_실행.bat --fullscreen
setlocal
cd /d "%~dp0"
title COFFEE ^& SPOON 키오스크 - 시연 모드
rem 가상환경 위치는 1_처음설치.bat 와 같다.
set "PY=%LOCALAPPDATA%\CoffeeSpoonKiosk\venv\Scripts\python.exe"

rem 가상환경이 없거나 설치가 덜 되었으면 1_처음설치.bat 로 준비부터 한다.
if exist "%PY%" "%PY%" -c "import PySide6, cryptography" >nul 2>&1 && goto run
echo 아직 준비가 안 되어 있어 준비부터 합니다.
rem 한글 파일 이름을 직접 쓰면 cmd 가 못 읽는 경우가 있어 1_*.bat 로 찾아 부른다.
for %%F in ("%~dp01_*.bat") do call "%%~fF" auto
if errorlevel 1 exit /b 1

:run
echo 시연 모드로 키오스크를 켭니다.  운영자 로그인: admin / demo   끄기: Ctrl+Shift+Q 또는 창 닫기
"%PY%" -m gui.main --demo %*
if errorlevel 1 goto fail
exit /b 0

:fail
echo.
echo 키오스크가 오류로 멈췄습니다. 이 창을 캡처해 보내 주세요. 오류 기록: logs\kiosk_error.log
pause
exit /b 1
