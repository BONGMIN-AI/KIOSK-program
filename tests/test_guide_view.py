"""얼굴 확인 창 화면(왼쪽 카메라 + 오른쪽 단계 안내) 테스트. 카메라 없이 가짜 프레임으로 그린다."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from face import guide_view


def face_at(cx, cy, size):
    """640x480 원본 프레임 좌표의 얼굴 박스 (YuNet 결과처럼 앞 4칸만 쓴다)."""
    return np.array([cx - size / 2, cy - size / 2, size, size], dtype=np.float32)


class GuideViewTest(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def test_steps_follow_the_random_motions(self):
        labels = guide_view.step_labels(["TURN RIGHT", "MOVE CLOSER"])
        self.assertEqual(labels[0], "타원 안에 얼굴 맞추기")
        self.assertEqual(labels[1:3], ["고개를 천천히 오른쪽으로", "카메라 쪽으로 조금 가까이"])
        self.assertEqual(labels[-1], "가운데로 돌아와 잠시 멈추기")

    def test_current_step_moves_down_in_order(self):
        self.assertEqual(guide_view.current_step(False, 0, 2), 0)
        self.assertEqual(guide_view.current_step(True, 0, 2), 1)
        self.assertEqual(guide_view.current_step(True, 1, 2), 2)
        self.assertEqual(guide_view.current_step(True, 2, 2), 3)

    def test_roi_accepts_centered_face_and_rejects_far_or_small_face(self):
        self.assertTrue(guide_view.frame_in_roi(self.frame, face_at(320, 250, 160)))
        self.assertFalse(guide_view.frame_in_roi(self.frame, face_at(120, 250, 160)))   # 옆으로 벗어남
        self.assertFalse(guide_view.frame_in_roi(self.frame, face_at(320, 250, 60)))    # 너무 멀어서 작음

    def test_compose_makes_side_by_side_window(self):
        canvas = guide_view.compose(self.frame, face_at(320, 250, 160), 1, ["TURN LEFT", "TURN RIGHT"],
                                    True, 1, "ENROLL", 0.5)
        self.assertEqual(canvas.shape, (720, 1280, 3))
        self.assertGreater(int(canvas[:, 640:].mean()), 200)   # 오른쪽은 흰 안내 패널

    def test_roi_color_shows_state(self):
        def roi_pixel(face, count=1, calibrated=False, motion_ok=False):
            canvas = guide_view.compose(self.frame, face, count, ["TURN LEFT", "TURN RIGHT"],
                                        calibrated, 0, "LOGIN", 0.0, motion_ok)
            cx, cy = guide_view.ROI_CENTER
            return tuple(int(v) for v in canvas[cy, cx - guide_view.ROI_AXES[0]])
        self.assertEqual(roi_pixel(face_at(320, 250, 160)), guide_view.GREEN)
        self.assertEqual(roi_pixel(None), guide_view.RED)
        self.assertEqual(roi_pixel(face_at(320, 250, 160), calibrated=True), guide_view.YELLOW)
        self.assertEqual(roi_pixel(face_at(320, 250, 160), calibrated=True, motion_ok=True), guide_view.GREEN)


if __name__ == "__main__":
    unittest.main()
