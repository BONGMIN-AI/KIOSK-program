"""10/29 얼굴 인증 교체 시험: F6 여러 장 비교·다른 회원 비교, F3·F4 품질 검사, 3번 실패 잠금.

카메라 없이 숫자 벡터와 가짜 프레임으로 시험한다. 실제 모델 파일이 있으면 지문도 확인한다.
"""
import hashlib
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.storage import MemoryVault
from domain.customers import (
    MAX_FACE_FAILURES, face_locked, login_with_face, login_with_password, register_customer,
    set_face_enrolled,
)
from face import SpoofError, quality
from face.opencv_face import judge_login


def unit(vector):
    vector = np.asarray(vector, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def near(base, noise, seed):
    """base와 닮은 얼굴 특징 (noise가 클수록 덜 닮음)."""
    rng = np.random.default_rng(seed)
    return unit(base + rng.normal(0, noise, base.shape))


class JudgeLoginTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.me = unit(rng.normal(size=512))
        self.other = unit(rng.normal(size=512))

    def test_same_person_passes(self):
        samples = np.vstack([near(self.me, 0.02, i) for i in range(5)])
        passed, text = judge_login(samples, self.me, {"C0002": self.other}, 0.45)
        self.assertTrue(passed)
        self.assertTrue(text.startswith("얼굴 유사도"))
        self.assertIn("5/5장", text)

    def test_other_person_fails(self):
        samples = np.vstack([near(self.other, 0.02, i) for i in range(5)])
        passed, _text = judge_login(samples, self.me, {}, 0.45)
        self.assertFalse(passed)

    def test_two_bad_frames_fail_even_if_mean_is_high(self):
        good = [near(self.me, 0.01, i) for i in range(3)]
        bad = [near(self.other, 0.01, i) for i in range(2)]
        passed, text = judge_login(np.vstack(good + bad), self.me, {}, 0.3)
        self.assertFalse(passed)
        self.assertIn("3/5장", text)

    def test_more_similar_to_another_member_fails(self):
        mixed = unit(self.me + self.other * 1.2)            # 두 사람 중간인데 다른 회원 쪽에 더 가까움
        samples = np.vstack([near(mixed, 0.005, i) for i in range(5)])
        passed, text = judge_login(samples, self.me, {"C0002": self.other}, 0.3)
        self.assertFalse(passed)
        self.assertIn("다른 등록 얼굴", text)


def frame_with_face(brightness=170, size=160):
    """얼굴 박스 + 5점(YuNet 형식)이 있는 가짜 프레임. 살색 바탕에 무늬를 넣어 흔들림 검사를 통과시킨다."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (brightness * 0.75, brightness * 0.85, brightness)        # BGR 살색 계열
    frame[::4, :] = np.clip(frame[::4, :].astype(int) - 40, 0, 255)      # 줄무늬 = 선명한 화면
    x, y = 320 - size / 2, 240 - size / 2
    s = size / 160
    face = np.array([x, y, size, size,
                     x + 50 * s, y + 60 * s, x + 110 * s, y + 60 * s,      # 눈 2개
                     x + 80 * s, y + 90 * s,                               # 코
                     x + 58 * s, y + 120 * s, x + 102 * s, y + 120 * s,    # 입꼬리 2개
                     0.95], dtype=np.float32)
    return frame, face


class QualityTest(unittest.TestCase):
    def test_clear_front_face_passes(self):
        frame, face = frame_with_face()
        self.assertEqual(quality.check(frame, face), "")

    def test_far_dark_turned_faces_are_rejected(self):
        frame, face = frame_with_face(size=70)
        self.assertEqual(quality.check(frame, face), quality.TOO_FAR)
        frame, face = frame_with_face(brightness=40)
        self.assertEqual(quality.check(frame, face), quality.TOO_DARK)
        frame, face = frame_with_face()
        face[8] += 40                                                     # 코가 옆으로 = 고개 돌림
        self.assertEqual(quality.check(frame, face), quality.NOT_FRONT)

    def test_mask_and_sunglasses(self):
        frame, face = frame_with_face()
        frame[int(face[11]) - 25:int(face[11]) + 30, int(face[10]) - 40:int(face[12]) + 40] = (235, 235, 235)
        self.assertEqual(quality.check(frame, face), quality.MASK)          # 흰 마스크
        frame, face = frame_with_face()
        for ex, ey in ((face[4], face[5]), (face[6], face[7])):
            frame[int(ey) - 12:int(ey) + 12, int(ex) - 16:int(ex) + 16] = (15, 15, 15)
        self.assertEqual(quality.check(frame, face), quality.EYES_COVERED)  # 선글라스


class NearFaceTest(unittest.TestCase):
    def test_only_faces_within_about_50cm(self):
        from face.opencv_face import OpenCVFace
        _frame, close = frame_with_face(size=160)
        _frame, far = frame_with_face(size=80)
        self.assertTrue(OpenCVFace._near(close, None))          # 웹캠: 얼굴 폭으로 판단
        self.assertFalse(OpenCVFace._near(far, None))
        depth = np.full((480, 640), 0.45, dtype=np.float32)     # D435: 코까지 45cm
        self.assertTrue(OpenCVFace._near(far, depth))
        depth[:] = 1.0                                          # 1m 뒤에 선 사람
        self.assertFalse(OpenCVFace._near(close, depth))

    def test_login_guide_has_no_ellipse_words(self):
        from face import guide_view
        canvas_args = (np.zeros((480, 640, 3), np.uint8), None, 0, ["LIVE CHECK"], False, 0, "LOGIN", 0.0)
        self.assertEqual(guide_view.step_labels(["LIVE CHECK"], "LOGIN")[0], "카메라 앞에 서기")
        self.assertEqual(guide_view.compose(*canvas_args).shape, (720, 1280, 3))


class Provider:
    """identify_face 결과를 정해 둔 가짜 얼굴 공급자."""

    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def identify_face(self, customer_id, on_status=print):
        if self.error:
            raise self.error
        return customer_id if self.result == "match" else None


class FaceLockTest(unittest.TestCase):
    def setUp(self):
        self.vault = MemoryVault()
        self.member = register_customer(self.vault, "가나다", "", "010-1111-2222", "member1", "pass1234",
                                        privacy_agreed=True)
        set_face_enrolled(self.vault, self.member["id"])

    def test_three_failures_lock_and_password_unlocks(self):
        for _ in range(MAX_FACE_FAILURES):
            with self.assertRaises(ValueError):
                login_with_face(self.vault, "member1", Provider(), lambda text: None)
        self.assertTrue(face_locked(self.vault, self.member["id"]))
        with self.assertRaisesRegex(ValueError, "잠겼어요"):
            login_with_face(self.vault, "member1", Provider("match"), lambda text: None)
        login_with_password(self.vault, "member1", "pass1234")
        self.assertFalse(face_locked(self.vault, self.member["id"]))
        login_with_face(self.vault, "member1", Provider("match"), lambda text: None)

    def test_photo_counts_but_cancel_does_not(self):
        from face import FaceError
        with self.assertRaises(FaceError):
            login_with_face(self.vault, "member1", Provider(error=FaceError("취소")), lambda text: None)
        self.assertEqual(self.vault.read("face_failures", default={}), {})
        with self.assertRaises(SpoofError):
            login_with_face(self.vault, "member1", Provider(error=SpoofError("사진")), lambda text: None)
        self.assertEqual(self.vault.read("face_failures")[self.member["id"]], 1)


class ModelFileTest(unittest.TestCase):
    def test_model_fingerprints(self):
        for path, expected in config.FACE_MODELS:
            if not Path(path).exists():
                self.skipTest(f"{Path(path).name} 없음 (tools/get_face_models.py)")
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
