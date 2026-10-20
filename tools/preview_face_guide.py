"""얼굴 확인 창(왼쪽 카메라 + 오른쪽 단계 안내)을 실제 카메라로 미리 본다.

메모리 저장소만 쓰므로 얼굴 특징·사진 어느 것도 저장하지 않는다. ESC로 끝낸다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.storage import MemoryVault
from face import FaceError, create_face_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="얼굴 확인 화면 미리 보기 (저장 없음)")
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    provider = create_face_provider(MemoryVault(), camera_index=args.camera)
    try:
        provider.verify_face(on_status=print)
        print("모든 단계 통과 (저장하지 않음)")
    except FaceError as exc:
        print(f"끝: {exc}")


if __name__ == "__main__":
    main()
