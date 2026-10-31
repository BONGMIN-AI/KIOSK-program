@echo off
chcp 65001 >nul
rem 첫 준비: 이미 있는 것은 건너뛰고, 없는 것만 안내한 뒤 키를 누르면 설치한다. 여러 번 실행해도 괜찮다.
rem 2_시연모드_실행.bat 가 준비가 안 되어 있을 때 "1_처음설치.bat auto" 로 부른다. auto 이면 끝난 뒤 멈추지 않고 모델도 묻지 않는다.
rem 가상환경은 저장소 폴더가 아니라 사용자 프로그램 폴더 %LOCALAPPDATA%\CoffeeSpoonKiosk\venv 에 만든다.
rem 저장소가 깊은 폴더에 있어도 Windows 경로 길이 한도(260자)에 걸리지 않게 하려는 것이다. 관리자 권한도 필요 없다.
setlocal
cd /d "%~dp0"
title COFFEE ^& SPOON 키오스크 - 첫 준비
set "VENV=%LOCALAPPDATA%\CoffeeSpoonKiosk\venv"
set "PY=%VENV%\Scripts\python.exe"
set "MODE=%~1"
set "NEED_VENV=0"
set "MISSING="

echo 설치 상태를 확인합니다...
echo 설치 위치: %VENV%
echo.
if not exist "%PY%" goto venv_missing
"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 goto venv_missing
echo   [있음] Python 가상환경
call :check PySide6 PySide6
call :check cryptography cryptography
call :check textual textual
call :check numpy numpy
call :check opencv-python cv2
call :check onnxruntime onnxruntime
call :check pillow PIL
call :check pyrealsense2 pyrealsense2
call :check pyserial serial
call :check pytest pytest
goto report

:venv_missing
set "NEED_VENV=1"
echo   [없음] Python 가상환경
set "MISSING= PySide6 cryptography textual numpy opencv-python onnxruntime pillow pyrealsense2 pyserial pytest"

:report
echo.
if "%NEED_VENV%%MISSING%"=="0" goto ready
echo 다음을 설치하겠습니다.
if "%NEED_VENV%"=="1" echo   - Python 가상환경 만들기: %VENV%
echo   - 프로그램 묶음:%MISSING%
echo   처음 설치는 인터넷으로 수백 MB를 받아 몇 분 걸립니다.
echo.
echo [Press any key to proceed]  아무 키나 누르면 설치를 시작합니다. 취소하려면 이 창을 닫으세요.
pause >nul
if "%NEED_VENV%"=="0" goto install

if exist "%VENV%" rmdir /s /q "%VENV%"
echo [1/2] Python 가상환경을 만듭니다...
set "BASE="
where py >nul 2>&1 && set "BASE=py -3"
if not defined BASE where python >nul 2>&1 && set "BASE=python"
if not defined BASE goto no_python
%BASE% -m venv "%VENV%"
if errorlevel 1 goto fail
"%PY%" -m pip install --upgrade pip --quiet

:install
echo [2/2] 프로그램 묶음을 설치합니다...
"%PY%" -m pip install -r requirements.txt pytest
if errorlevel 1 goto fail
echo 설치 완료.
goto models

:ready
echo 이미 모두 설치되어 있어 설치를 건너뜁니다.

:models
echo.
if not exist "models\face_recognition_arcface_w600k_r50.onnx" goto model_missing
echo   [있음] 얼굴 인증 모델 ArcFace
goto done

:model_missing
echo   [없음] 얼굴 인증 모델 ArcFace - 시연 모드에는 필요 없고, 실제 모드 얼굴 로그인에만 필요합니다.
if /i "%MODE%"=="auto" goto done
choice /c YN /m "지금 인터넷에서 받을까요? 약 300MB"
if errorlevel 2 goto done
"%PY%" tools\get_face_models.py
if errorlevel 1 echo 모델 받기에 실패했습니다. 나중에 1_처음설치.bat 를 다시 실행하세요.

:done
echo.
echo 준비 끝! 이제 2_시연모드_실행.bat 를 더블클릭하면 시연 모드가 켜집니다.
if /i not "%MODE%"=="auto" pause
exit /b 0

rem 사용: call :check 설치이름 import이름  - 없으면 MISSING 에 더한다
:check
"%PY%" -c "import %~2" >nul 2>&1
if errorlevel 1 goto check_missing
echo   [있음] %~1
exit /b 0
:check_missing
echo   [없음] %~1
set "MISSING=%MISSING% %~1"
exit /b 0

:no_python
echo Python 을 찾지 못했습니다. https://www.python.org 에서 Python 3 를 설치할 때
echo "Add python.exe to PATH" 를 체크하고, 설치 후 이 파일을 다시 실행하세요.
pause
exit /b 1

:fail
echo.
echo 설치 중 오류가 났습니다. 인터넷 연결을 확인하고 1_처음설치.bat 를 다시 실행하세요.
echo 계속 안 되면 이 창을 캡처해 보내 주세요.
pause
exit /b 1
