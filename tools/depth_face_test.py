"""D435 깊이로 입체 얼굴 판정을 실시간으로 시험한다. 영상·깊이·얼굴 특징 어느 것도 저장하지 않는다.

창: 왼쪽 컬러(눈·코·입꼬리 점과 판정), 오른쪽 깊이 색 지도. ESC로 끝낸다.
진짜 얼굴 → 3D FACE OK, 휴대폰 화면·인쇄 사진 → FLAT 이 나오면 정상이다.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from core.storage import MemoryVault
from face import create_face_provider
from face.depth_check import DepthVote, RealSenseCamera, judge, realsense_available

GREEN, RED, YELLOW = (70, 200, 70), (40, 40, 230), (0, 200, 255)


def main() -> None:
    parser = argparse.ArgumentParser(description="D435 입체 얼굴 판정 시험 (저장 없음)")
    parser.add_argument("--seconds", type=float, default=60)
    args = parser.parse_args()
    if not realsense_available():
        raise SystemExit("RealSense 카메라를 찾지 못했습니다. D435를 USB 3 포트에 꽂아 주세요")
    detector = create_face_provider(MemoryVault())   # YuNet 얼굴 찾기만 쓴다 (카메라는 열지 않음)
    vote = DepthVote()
    title = "DEPTH FACE TEST (ESC: quit)"
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title, 1280, 480)
    print("진짜 얼굴 → 휴대폰 화면 속 얼굴 → 인쇄 사진 순서로 비춰 보세요. ESC로 끝냅니다.")
    started = last = time.monotonic()
    with RealSenseCamera() as cam:
        while time.monotonic() - started < args.seconds:
            color, depth = cam.read()
            if color is None:
                continue
            face, count, _far = detector._detect_one(color, depth)
            view = color.copy()
            if face is None:
                label, col, line = (f"FACES: {count}", RED, f"얼굴 {count}개")
            else:
                result = judge(depth, face)
                vote.add(result.ok)
                for i in range(4, 14, 2):
                    cv2.circle(view, (int(face[i]), int(face[i + 1])), 4, YELLOW, -1)
                nose = "-" if result.nose_mm is None else f"{result.nose_mm:+.1f}mm"
                dist = "-" if result.distance_m is None else f"{result.distance_m:.2f}m"
                if vote.passed:
                    label, col = f"3D FACE OK  nose {nose}  dist {dist}", GREEN
                elif vote.decided:
                    label, col = f"FLAT / REJECT  nose {nose}  dist {dist}", RED
                else:
                    label, col = f"MEASURING...  nose {nose}  dist {dist}", YELLOW
                line = f"코 돌출 {nose}, 거리 {dist}, 이번 프레임: {result.reason}, 최근 10장 통과 {sum(vote.history)}"
            cv2.rectangle(view, (0, 0), (640, 40), (20, 20, 20), -1)
            cv2.putText(view, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, col, 2, cv2.LINE_AA)
            depth_mm = np.clip(depth * 1000, 200, 1500)
            depth_vis = cv2.applyColorMap(((depth_mm - 200) / 1300 * 255).astype(np.uint8), cv2.COLORMAP_JET)
            depth_vis[depth <= 0] = 0
            cv2.imshow(title, np.hstack([view, depth_vis]))
            if time.monotonic() - last >= 0.7:
                last = time.monotonic()
                print(f"{last - started:5.1f}s  {line}")
            if cv2.waitKey(1) & 0xFF == 27:
                break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
