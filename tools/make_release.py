"""배포용 실행 폴더를 만든다. 사용: python tools/make_release.py [만들 폴더]

기본 위치는 팀장 PC의 작업 폴더 AI프로젝트\최신본_2026-10-19\07_배포_실행폴더\COFFEE_SPOON_KIOSK 이고,
그 폴더가 없는 PC에서는 바탕화면의 COFFEE_SPOON_KIOSK 이다. 이 폴더를 그대로 압축해 나눠 주면
받은 사람은 setup.bat → run_kiosk.bat 순서로 더블클릭해 실행한다.

넣는 것은 GUI 키오스크 실행에 필요한 코드·그림·작은 얼굴 모델·실행 파일뿐이다.
테스트·문서·예전 터미널(TUI) 화면·개인정보(data/)·오류 기록(logs/)은 넣지 않는다.
ArcFace 모델(약 170MB, 비상업 연구용)도 넣지 않고, 받은 사람의 setup.bat 가 내려받기를 묻는다.

다시 실행하면 아래 목록의 파일만 새로 바꾼다. 받은 폴더에서 시험하며 생긴 data/·logs/·
내려받은 ArcFace 모델은 지우지 않는다.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = Path.home() / "Desktop" / "AI프로젝트" / "최신본_2026-10-19" / "07_배포_실행폴더"
DEFAULT_TARGET = (RELEASE_DIR if RELEASE_DIR.is_dir() else Path.home() / "Desktop") / "COFFEE_SPOON_KIOSK"

FOLDERS = ["core", "domain", "face", "gui"]
FILES = [
    "setup.bat",
    "run_kiosk.bat",
    "run_kiosk_real.bat",
    "config.py",
    "requirements.txt",
    "models/README.md",
    "models/face_detection_yunet_2026may.onnx",
    "models/antispoof_minifasnet_v2.onnx",
    "models/antispoof_minifasnet_v1se.onnx",
    "tools/run_kiosk.bat",
    "tools/reset_data.py",
    "tools/get_face_models.py",
    "tools/check_camera.py",
    "tools/register_face.py",
]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")


def build(target: Path) -> None:
    if target.resolve() == ROOT or ROOT in target.resolve().parents:
        raise SystemExit("저장소 폴더 안에는 만들 수 없습니다. 다른 위치를 고르세요.")
    target.mkdir(parents=True, exist_ok=True)
    for name in FOLDERS:
        shutil.rmtree(target / name, ignore_errors=True)
        shutil.copytree(ROOT / name, target / name, ignore=SKIP)
    for name in FILES:
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target / name)
    print(f"배포 폴더를 만들었습니다: {target}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET)
