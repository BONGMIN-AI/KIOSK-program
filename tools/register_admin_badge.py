"""관리자 카드 등록 (11/04 회의): 카드 한 장 + 운영자 본인 얼굴. 본인이 카메라 앞에서 직접 한다.

사용: python tools/register_admin_badge.py            카드 대기 → 얼굴 등록 → data/admin_badge.bin 저장
      python tools/register_admin_badge.py --remove   관리자 카드 지우기
키오스크를 끄고 실행한다 (카드 리더 포트를 같이 못 씀). 저장 파일은 이 PC의 이 Windows 계정에서만 풀린다.
얼굴은 사진이 아니라 특징값(숫자)만 저장한다. 등록하면 키오스크 처음 화면에서 이 카드를 대고 얼굴을 보면 운영자 화면으로 간다.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from core import admin_badge
from domain.customers import card_hash
from gui.serial_card import BAUD, find_port, parse_line

WAIT_SECONDS = 60


def read_card():
    import serial
    port = find_port()
    if not port:
        raise SystemExit("카드 리더(RC카 나노)를 찾지 못했어요. USB를 꽂고 다시 실행해 주세요")
    try:
        link = serial.Serial(port, BAUD, timeout=0.5)
    except serial.SerialException:
        raise SystemExit(f"{port}를 다른 프로그램이 쓰고 있어요. 키오스크 · 카드 리더 시험 창을 끄고 다시 실행해 주세요")
    print(f"{port} 연결. 아두이노가 켜지는 데 2초쯤 걸려요.")
    print(f"관리자 카드로 쓸 카드를 리더기에 대 주세요 ({WAIT_SECONDS}초 안에)…", flush=True)
    end = time.monotonic() + WAIT_SECONDS
    with link:
        while time.monotonic() < end:
            number = parse_line(link.readline().decode("ascii", errors="ignore"))
            if number:
                return number
    raise SystemExit("카드를 읽지 못했어요. 다시 실행해 주세요")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if "--remove" in sys.argv:
        if admin_badge.PATH.exists():
            admin_badge.PATH.unlink()
        print("관리자 카드를 지웠어요")
        return
    number = read_card()
    print(f"카드 확인: ****{number[-4:]}")
    admin_badge.save({"card_hash": card_hash(number), "face_profiles": {}})
    print("\n이제 운영자 본인 얼굴을 등록해요. 카메라 창이 뜨면 50cm 안에서 정면을 보고 잠시 멈춰 주세요 (ESC 취소).", flush=True)
    from face import FaceError
    from face.opencv_face import OpenCVFace
    try:
        OpenCVFace(admin_badge.BadgeVault(), config.CAMERA_INDEX).enroll_face(admin_badge.ADMIN_KEY)
    except FaceError as error:
        admin_badge.PATH.unlink(missing_ok=True)
        raise SystemExit(f"얼굴 등록을 못 했어요 · {error}\n카드도 지웠어요. 다시 실행해 주세요")
    finally:
        try:
            import cv2
            cv2.destroyAllWindows()
        except Exception:
            pass
    data = admin_badge.load()
    print(f"\n완료! 관리자 카드 ****{number[-4:]} + 얼굴 특징을 저장했어요 → {admin_badge.PATH}")
    print("키오스크 처음 화면에서 이 카드를 대고 카메라를 보면 운영자 화면으로 들어가요.")
    print("※ 이 카드는 회원카드로 쓰지 마세요." if data.get("card_hash") else "")


if __name__ == "__main__":
    main()
