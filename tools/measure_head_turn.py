"""고개 좌우 각도(yaw) 값을 15초 동안 찍어 본다. 창도 저장도 없다.

정면 → 자기 왼쪽으로 고개 → 정면 → 자기 오른쪽으로 고개 순서로 해 보면
왼쪽이 음수, 오른쪽이 양수로 나와야 판정 방향이 맞다.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from core.storage import MemoryVault
from face import create_face_provider, quality


def main() -> None:
    parser = argparse.ArgumentParser(description="고개 좌우 각도 측정 (저장 없음)")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=15)
    args = parser.parse_args()
    provider = create_face_provider(MemoryVault(), camera_index=args.camera)
    cap = provider._open_camera()
    print("정면 → 자기 왼쪽으로 고개 → 정면 → 자기 오른쪽으로 고개 (몸은 그대로)")
    started = last = time.monotonic()
    try:
        while time.monotonic() - started < args.seconds:
            ok, frame = cap.read()
            if not ok:
                continue
            face, count, _far = provider._detect_one(cv2.flip(frame, 1))
            if time.monotonic() - last >= 0.5:
                last = time.monotonic()
                t = last - started
                if face is None:
                    print(f"{t:5.1f}s  얼굴 {count}개")
                else:
                    yaw = quality.yaw(face)
                    bar = "<" * int(max(0, -yaw) * 20) + "|" + ">" * int(max(0, yaw) * 20)
                    print(f"{t:5.1f}s  yaw {yaw:+.2f}  {bar}")
    finally:
        cap.release()


if __name__ == "__main__":
    main()
