r"""기존 회원에게 실제 카메라 얼굴 특징을 등록한다.

예: .\.venv\Scripts\python.exe tools\register_face.py --login-id bomin
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core import auth
from domain.customers import find_by_login_id, set_face_enrolled
from face import create_face_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="기존 KIOSK 회원 얼굴 등록")
    parser.add_argument("--login-id", default="bomin", help="얼굴을 등록할 회원 ID")
    parser.add_argument("--admin", default="admin", help="금고 관리자 ID")
    parser.add_argument("--camera", type=int, default=0, help="웹캠 번호 (기본 0)")
    args = parser.parse_args()

    if not config.KEYSTORE_PATH.exists():
        raise SystemExit("먼저 tools/reset_data.py --yes 로 데이터를 초기화하세요")
    password = getpass.getpass("관리자 비밀번호: ")
    vault = auth.unlock(config.KEYSTORE_PATH, config.DATA_DIR, args.admin, password)
    customer = find_by_login_id(vault, args.login_id)
    if not customer:
        raise SystemExit(f"회원 ID를 찾을 수 없습니다: {args.login_id}")

    print(f"등록 대상: {customer['extra']['nickname']} ({customer['id']})")
    print("정면 보정 뒤 화면에 나오는 무작위 동작 2개를 따라 하세요. ESC는 취소입니다.")
    provider = create_face_provider(vault, camera_index=args.camera)
    provider.enroll_face(customer["id"], print)
    set_face_enrolled(vault, customer["id"], True)
    print("완료: 이제 앱에서 회원 ID + 얼굴 로그인을 사용할 수 있습니다.")


if __name__ == "__main__":
    main()
