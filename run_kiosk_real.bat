@echo off
chcp 65001 >nul
rem 실제 모드: data\ 암호화 금고와 카메라를 쓴다. 첫 화면에서 관리자 ID admin 과 비밀번호로 금고를 연다.
rem 매장처럼 전체 화면 + 멈추면 자동 재시작으로 돌리려면 tools\run_kiosk.bat 를 쓴다.
setlocal
cd /d "%~dp0"
title COFFEE ^& SPOON 키오스크 - 실제 모드

rem USB 카메라를 쓰면 아래 0 을 카메라 번호로 바꾼다. 팀장 노트북 USB 카메라는 2.
if not defined KIOSK_CAMERA set "KIOSK_CAMERA=0"

rem 가상환경 위치는 setup.bat 와 같다.
set "PY=%LOCALAPPDATA%\CoffeeSpoonKiosk\venv\Scripts\python.exe"
rem 가상환경이 없거나 설치가 덜 되었으면 setup.bat 로 준비부터 한다.
if exist "%PY%" "%PY%" -c "import PySide6, cryptography, cv2, onnxruntime" >nul 2>&1 && goto check_data
echo 아직 준비가 안 되어 있어 준비부터 합니다.
call setup.bat auto
if errorlevel 1 exit /b 1

:check_data
if exist "data\keystore.json" goto check_model
echo 아직 금고 데이터가 없습니다. 시연 데이터를 만들고 관리자 비밀번호를 새로 정합니다.
"%PY%" tools\reset_data.py --yes
if errorlevel 1 goto fail

:check_model
if exist "models\face_recognition_arcface_w600k_r50.onnx" goto run
echo 주의: 얼굴 인증 모델이 없어 얼굴 로그인이 안 됩니다. 비밀번호 로그인은 됩니다.
echo       setup.bat 를 실행해 모델을 받을 수 있습니다.

:run
echo 실제 모드로 켭니다. 카메라 번호: %KIOSK_CAMERA%   끄기: Ctrl+Shift+Q 또는 창 닫기
"%PY%" -m gui.main %*
if errorlevel 1 goto fail
exit /b 0

:fail
echo.
echo 오류로 멈췄습니다. 이 창을 캡처해 보내 주세요. 오류 기록: logs\kiosk_error.log
pause
exit /b 1
