r"""배포용 실행 폴더를 만든다. 사용: python tools/make_release.py [만들 폴더] [--zip]

기본 위치는 팀장 PC의 작업 폴더 AI프로젝트\최신본_2026-10-19\07_배포_실행폴더\COFFEE_SPOON_KIOSK_v1.0 이고,
그 폴더가 없는 PC에서는 바탕화면의 COFFEE_SPOON_KIOSK_v1.0 이다. --zip 이면 같은 이름의 .zip도 만든다.

받은 사람이 보는 맨 위에는 실행 방법 한 장과 더블클릭할 파일 세 개만 둔다 (11/01: 처음 쓰는 사람용으로 줄임):

    COFFEE_SPOON_KIOSK_v1.0\
      0_실행방법.html                                              ← 먼저 여는 한 장 (압축 풀기 → Python → 1 → 2)
      1_처음설치.bat · 2_시연모드_실행.bat · 3_실제모드_실행.bat   ← program\ 안의 같은 이름 파일을 부르는 짧은 실행 파일
      문서\   사용설명서 · 최종보고서 · 추가 구현 아이디어 · 시나리오 점검 결과(그림 포함)
      program\   실제 프로그램 (코드 · 그림 · 작은 얼굴 모델 · 원래 실행 파일 · 도구 · RFID 아두이노 코드)

program\ 에는 GUI 키오스크 실행에 필요한 것만 넣는다. 테스트·개발 문서·예전 터미널(TUI) 화면·
개인정보(data\)·오류 기록(logs\)은 넣지 않는다. ArcFace 모델(약 170MB, 비상업 연구용)도 넣지 않고,
받은 사람의 1_처음설치.bat 가 내려받기를 묻는다.

다시 실행하면 아래 목록의 파일만 새로 바꾼다. 받은 폴더에서 시험하며 생긴 program\data\·program\logs\·
내려받은 ArcFace 모델은 지우지 않는다.
"""
import os
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = Path.home() / "Desktop" / "AI프로젝트" / "최신본_2026-10-19"
RELEASE_DIR = WORK / "07_배포_실행폴더"
DEFAULT_TARGET = (RELEASE_DIR if RELEASE_DIR.is_dir() else Path.home() / "Desktop") / "COFFEE_SPOON_KIOSK_v1.0"
SCENARIO_RESULT = WORK / "08_최종점검" / "시나리오_점검"      # tools/run_scenarios.py 결과
DOCS = ROOT / "docs" / "release"

FOLDERS = ["core", "domain", "face", "gui", "tools/arduino"]
FILES = [
    "1_처음설치.bat",
    "2_시연모드_실행.bat",
    "3_실제모드_실행.bat",
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
    "tools/check_card_reader.py",
]
OLD_TOP_FILES = ["빠른_시작_안내.html", "사용설명서.html", "먼저_읽어주세요.txt"]   # 예전 배포판 맨 위 파일 (지운다)
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")

# 맨 위 실행 파일: program\ 안의 원래 실행 파일을 부른다. 한글 파일 이름을 직접 쓰면 cmd가 못 읽는 경우가 있어
# 1_*.bat 처럼 번호로 찾는다 (원래 실행 파일들과 같은 방법).
LAUNCHER = """@echo off
chcp 65001 >nul
rem 실제 프로그램은 program 폴더에 있다. 이 파일은 program 안의 같은 번호 실행 파일을 부른다.
for %%F in ("%~dp0program\\{number}_*.bat") do call "%%~fF" %*
"""

def clear_readonly_and_retry(func, path, _error):
    """바탕화면 아래 폴더는 Windows가 읽기 전용 표시를 붙여 지우기가 실패한다. 표시를 떼고 다시 지운다."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, onexc=clear_readonly_and_retry)
    elif path.exists():
        path.unlink()


def write_text(path: Path, text: str, encoding="utf-8") -> None:
    """Windows 실행 파일·메모장이 잘 읽도록 줄 끝을 CRLF로 쓴다."""
    path.write_bytes(text.replace("\n", "\r\n").encode(encoding))


def copy_page(source: Path, target: Path, replace=()) -> None:
    text = source.read_text(encoding="utf-8")
    for old, new in replace:
        text = text.replace(old, new)
    target.write_text(text, encoding="utf-8")


def build_program(program: Path) -> None:
    program.mkdir(parents=True, exist_ok=True)
    for name in FOLDERS:
        remove(program / name)
        shutil.copytree(ROOT / name, program / name, ignore=SKIP)
    for name in FILES:
        (program / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, program / name)


def build_docs(target: Path) -> None:
    docs = target / "문서"
    docs.mkdir(exist_ok=True)
    remove(docs / "images")
    shutil.copytree(DOCS / "images", docs / "images")
    copy_page(DOCS / "0_실행방법.html", target / "0_실행방법.html")
    copy_page(DOCS / "사용설명서.html", docs / "사용설명서.html")
    for name in OLD_TOP_FILES:
        remove(target / name)
    copy_page(DOCS / "최종보고서.html", docs / "최종보고서.html",
              [("<code>문서\\시나리오_점검결과.html</code>", '<a href="시나리오_점검결과.html">시나리오_점검결과.html</a>')])
    copy_page(DOCS / "추가_구현_아이디어.html", docs / "추가_구현_아이디어.html")
    if (SCENARIO_RESULT / "점검결과.html").exists():
        remove(docs / "시나리오_화면")
        shutil.copytree(SCENARIO_RESULT / "화면", docs / "시나리오_화면")
        copy_page(SCENARIO_RESULT / "점검결과.html", docs / "시나리오_점검결과.html",
                  [('src="화면/', 'src="시나리오_화면/')])
    else:
        print(f"주의: 시나리오 점검 결과가 없어 넣지 못했습니다 ({SCENARIO_RESULT}). "
              "python tools/run_scenarios.py 를 먼저 실행하세요.")


def build(target: Path, make_zip: bool = False) -> None:
    if target.resolve() == ROOT or ROOT in target.resolve().parents:
        raise SystemExit("저장소 폴더 안에는 만들 수 없습니다. 다른 위치를 고르세요.")
    target.mkdir(parents=True, exist_ok=True)
    build_program(target / "program")
    for number, name in ((1, "1_처음설치.bat"), (2, "2_시연모드_실행.bat"), (3, "3_실제모드_실행.bat")):
        write_text(target / name, LAUNCHER.format(number=number))
    build_docs(target)
    print(f"배포 폴더를 만들었습니다: {target}")
    if make_zip:
        archive = shutil.make_archive(str(target), "zip", root_dir=target.parent, base_dir=target.name)
        print(f"압축 파일: {archive}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--zip"]
    target = Path(args[0]) if args else DEFAULT_TARGET
    # 압축에는 폴더 전체가 들어가므로, 시험하며 생긴 개인정보·기록이 있는 폴더는 압축하지 않는다
    if "--zip" in sys.argv and ((target / "program" / "data").exists() or (target / "program" / "logs").exists()):
        raise SystemExit("program\\data 또는 logs 가 있어 압축하지 않습니다 (개인정보·기록이 섞일 수 있음). "
                         "새 폴더에 만들어 압축하세요.")
    build(target, make_zip="--zip" in sys.argv)
