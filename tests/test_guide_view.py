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

    def test_steps_are_short_without_technical_words(self):
        labels = guide_view.step_labels(["LIVE CHECK"])
        self.assertEqual(labels, ["카메라 앞에 서기", "정면을 보고 잠시 멈추기", "확인 중"])
        self.assertNotIn("입체", " ".join(guide_view.step_labels(["DEPTH CHECK"], "LOGIN")))

    def test_enroll_also_shows_face_symbol_not_camera(self):
        """10/29: 등록도 타원에 맞추지 않고 얼굴 기호만 (50cm 안이면 된다)."""
        dark = np.full((480, 640, 3), 30, dtype=np.uint8)
        canvas = guide_view.compose(dark, face_at(320, 250, 160), 1, ["LIVE CHECK"], False, 0, "ENROLL", 0.1,
                                    alert="입이 가려졌어요. 마스크를 벗어 주세요")
        self.assertGreater(int(canvas[10, 10].mean()), 200)     # 왼쪽은 영상 대신 밝은 바탕

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
        canvas = guide_view.compose(self.frame, face_at(320, 250, 160), 1, ["LIVE CHECK"],
                                    True, 1, "ENROLL", 0.5)
        self.assertEqual(canvas.shape, (720, 1280, 3))
        self.assertGreater(int(canvas[:, 640:].mean()), 200)   # 오른쪽은 흰 안내 패널

    def test_login_shows_face_symbol_not_camera(self):
        bright = np.full((480, 640, 3), 30, dtype=np.uint8)     # 어두운 카메라 영상
        canvas = guide_view.compose(bright, face_at(320, 250, 160), 1, ["DEPTH CHECK"], True, 0, "LOGIN", 0.3)
        self.assertGreater(int(canvas[10, 10].mean()), 200)     # 왼쪽은 영상 대신 밝은 바탕
        done = guide_view.compose(bright, face_at(320, 250, 160), 1, ["DEPTH CHECK"], True, 1, "LOGIN",
                                  1.0, True, done=True)
        cx, cy = guide_view.ROI_CENTER
        self.assertEqual(tuple(int(v) for v in done[cy - 220, cx]), (90, 190, 70))   # 눈금 고리 전부 초록
        self.assertEqual(guide_view.step_labels(["DEPTH CHECK"], "LOGIN")[0], "카메라 앞에 서기")


if __name__ == "__main__":
    unittest.main()
