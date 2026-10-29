"""데이터를 깨끗하게 초기화하고 시연용 샘플을 다시 채운다.

사용:  python tools/reset_data.py --yes
       (관리자 비밀번호는 입력창에서 묻는다. 자동화할 때만 --password 사용)
domain/seed.py 에 run(vault) 함수가 있으면 샘플 데이터를 자동으로 채운다.
"""
import argparse
import getpass
import importlib
import importlib.util
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core import auth, schema


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--admin", default="admin")
    p.add_argument("--password")
    p.add_argument("--yes", action="store_true", help="data/ 폴더를 지우는 것에 동의")
    args = p.parse_args()
    if not args.yes:
        # VS Code ▶ 버튼처럼 --yes 없이 실행했을 때는 여기서 한 번 더 묻는다.
        answer = input("data/ 폴더의 모든 데이터가 삭제됩니다. 계속하려면 yes 를 입력하세요: ")
        if answer.strip().lower() != "yes":
            sys.exit("취소했습니다. 데이터는 그대로입니다.")
    password = args.password or getpass.getpass("새 관리자 비밀번호 (입력해도 화면에 안 보임): ")
    if len(password) < 4:
        sys.exit("비밀번호는 4자 이상이어야 합니다. 데이터는 그대로입니다.")

    shutil.rmtree(config.DATA_DIR, ignore_errors=True)
    if config.KEYSTORE_PATH.exists():
        sys.exit("data/ 폴더를 지우지 못했습니다. KIOSK 프로그램이나 data 폴더를 연 창을 닫고 다시 실행하세요.")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    auth.init_keystore(config.KEYSTORE_PATH, args.admin, password)
    vault = auth.unlock(config.KEYSTORE_PATH, config.DATA_DIR, args.admin, password)
    vault.write("settings", schema.DEFAULT_SETTINGS)

    if importlib.util.find_spec("domain.seed"):
        seed = importlib.import_module("domain.seed")
        seed.run(vault)
        if hasattr(seed, "add_demo_events"):
            seed.add_demo_events(vault)
        print("샘플 데이터를 채웠습니다.")
    else:
        print("domain/seed.py 가 없어 샘플은 건너뜁니다.")
    print(f"초기화 완료. 관리자 ID: {args.admin}")


if __name__ == "__main__":
    main()
