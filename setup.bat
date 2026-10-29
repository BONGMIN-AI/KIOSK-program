@echo off
chcp 65001 >nul
rem 첫 준비: .venv 가상환경을 만들고 requirements.txt 를 설치한다. 여러 번 실행해도 괜찮다.
rem run_kiosk.bat 가 .venv 가 없을 때 "setup.bat auto" 로 부른다. auto 이면 질문·멈춤 없이 진행한다.
setlocal
cd /d "%~dp0"
title COFFEE ^& SPOON 키오스크 - 첫 준비
set "PY=.venv\Scripts\python.exe"
set "MODE=%~1"

if not exist "%PY%" goto make_venv
"%PY%" -c "import sys" >nul 2>&1
if not errorlevel 1 goto install
echo .venv 가 고장나 있어 새로 만듭니다.
rmdir /s /q .venv

:make_venv
echo [1/3] 가상환경 .venv 를 만듭니다...
set "BASE="
where py >nul 2>&1 && set "BASE=py -3"
if not defined BASE where python >nul 2>&1 && set "BASE=python"
if not defined BASE goto no_python
%BASE% -m venv .venv
if errorlevel 1 goto fail

:install
echo [2/3] 필요한 프로그램을 설치합니다. 처음에는 몇 분 걸립니다...
"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install -r requirements.txt pytest
if errorlevel 1 goto fail

echo [3/3] 얼굴 인증 모델을 확인합니다...
if exist "models\face_recognition_arcface_w600k_r50.onnx" goto done
echo 얼굴 인증 모델 ArcFace 파일이 없습니다. 시연 모드에는 필요 없고, 실제 모드 얼굴 로그인에만 필요합니다.
if /i "%MODE%"=="auto" goto done
choice /c YN /m "지금 인터넷에서 받을까요? 약 300MB"
if errorlevel 2 goto done
"%PY%" tools\get_face_models.py
if errorlevel 1 echo 모델 받기에 실패했습니다. 나중에 setup.bat 를 다시 실행하세요.

:done
echo.
echo 준비 끝! 이제 run_kiosk.bat 를 더블클릭하면 시연 모드가 켜집니다.
if /i not "%MODE%"=="auto" pause
exit /b 0

:no_python
echo Python 을 찾지 못했습니다. https://www.python.org 에서 Python 3 를 설치할 때
echo "Add python.exe to PATH" 를 체크하고, 설치 후 이 파일을 다시 실행하세요.
pause
exit /b 1

:fail
echo.
echo 준비 중 오류가 났습니다. 인터넷 연결을 확인하고 setup.bat 를 다시 실행하세요.
echo 계속 안 되면 이 창을 캡처해 보내 주세요.
pause
exit /b 1
