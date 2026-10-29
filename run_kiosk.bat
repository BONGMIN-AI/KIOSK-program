@echo off
chcp 65001 >nul
rem 시연 모드: 메모리 샘플 데이터로 켠다. 비밀번호·data 폴더·카메라가 없어도 되고 저장되지 않는다.
rem 운영자 로그인은 admin / demo. 전체 화면으로 보려면 명령창에서  run_kiosk.bat --fullscreen
setlocal
cd /d "%~dp0"
title COFFEE ^& SPOON 키오스크 - 시연 모드
set "PY=.venv\Scripts\python.exe"

if exist "%PY%" goto run
echo 처음 실행이라 준비부터 합니다. 몇 분 걸립니다...
call setup.bat auto
if errorlevel 1 goto fail

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
