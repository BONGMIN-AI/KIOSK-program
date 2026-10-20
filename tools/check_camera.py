"""카메라와 OpenCV 모델을 짧게 점검한다. 사진은 저장하지 않는다."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.storage import MemoryVault
from face import create_face_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="KIOSK 카메라 연결 점검")
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    provider = create_face_provider(MemoryVault(), camera_index=args.camera)
    if not provider.camera_available():
        raise SystemExit("카메라는 열렸지만 프레임을 읽지 못했습니다")
    print(f"카메라 {args.camera}번과 얼굴 모델 점검 완료 (이미지 저장 없음)")


if __name__ == "__main__":
    main()
