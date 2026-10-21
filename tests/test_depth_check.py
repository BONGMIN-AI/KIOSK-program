"""깊이 입체 얼굴 판정 테스트. 카메라 없이 가짜 깊이 영상으로 확인한다."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from face import depth_check as dc

# 640x480 프레임 좌표의 YuNet 형식 얼굴 (박스 + 눈2·코·입꼬리2 + 점수)
FACE = np.array([240, 160, 160, 180,
                 280, 220, 360, 220,      # 눈1, 눈2
                 320, 265,                # 코
                 290, 305, 350, 305,      # 입꼬리1, 입꼬리2
                 0.95], dtype=np.float32)


def plane(base_m=0.5, tilt_x=0.0, tilt_y=0.0):
    ys, xs = np.mgrid[0:480, 0:640].astype(np.float32)
    return base_m + tilt_x * (xs - 320) + tilt_y * (ys - 240)


def with_nose(depth, mm):
    depth = depth.copy()
    depth[255:276, 310:331] -= mm / 1000.0      # 코 주변이 카메라 쪽으로 mm만큼 나옴
    return depth


class DepthCheckTest(unittest.TestCase):
    def test_flat_photo_is_rejected_even_when_tilted(self):
        for depth in (plane(), plane(tilt_x=0.0004), plane(tilt_y=-0.0005)):
            result = dc.judge(depth, FACE)
            self.assertFalse(result.ok)
            self.assertLess(abs(result.nose_mm), 2.0)

    def test_real_face_with_nose_passes(self):
        result = dc.judge(with_nose(plane(tilt_x=0.0003), 20), FACE)
        self.assertTrue(result.ok, result.reason)
        self.assertAlmostEqual(result.nose_mm, 20, delta=1.0)
        self.assertAlmostEqual(result.distance_m, 0.5, delta=0.05)

    def test_missing_depth_and_bad_distance(self):
        depth = with_nose(plane(), 20)
        depth[260:270, 315:325] = 0                # 코 부분 측정 실패
        self.assertIn("재지 못했", dc.judge(depth, FACE).reason)
        far = dc.judge(with_nose(plane(base_m=2.0), 20), FACE)
        self.assertFalse(far.ok)
        self.assertIn("거리", far.reason)

    def test_vote_needs_most_recent_frames(self):
        vote = dc.DepthVote(window=10, need=7)
        for ok in [False] * 4 + [True] * 6:
            vote.add(ok)
        self.assertTrue(vote.decided)
        self.assertFalse(vote.passed)          # 10장 중 6장 통과
        vote.add(True)                         # 가장 오래된 실패 1장이 빠지고 7장 통과
        self.assertTrue(vote.passed)


if __name__ == "__main__":
    unittest.main()
