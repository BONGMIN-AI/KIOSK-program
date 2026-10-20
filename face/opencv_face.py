"""OpenCV YuNet + SFace 기반 로컬 얼굴 등록·로그인.

사진과 영상 프레임은 저장하지 않는다. SFace가 만든 128차원 특징값만 기존
Vault의 ``face_profiles`` 데이터셋에 저장하므로 디스크에서는 암호화된다.
등록 때는 무작위 동작 두 가지, 로그인 때는 한 가지를 요구해 정지 사진 공격을 줄인다.
고개 돌림은 YuNet이 함께 주는 눈·코 위치로 좌우 각도(yaw)를 추정해 판정한다.

이 활성 생체 확인은 수업용 데모 수준이다. 움직이는 영상·정교한 3D 마스크까지
막는 상용 위조 방지 시스템은 아니다.
"""
from __future__ import annotations

import hashlib
import random
import time
from pathlib import Path

import cv2
import numpy as np

import config
from core.schema import now_iso
from . import FaceError, guide_view


COSINE_THRESHOLD = 0.363
SESSION_SECONDS = 45
CAPTURE_SAMPLES = 10          # 등록: 정면 특징 10장 평균
LOGIN_SAMPLES = 5             # 로그인·확인: 빠르게 5장
TURN_THRESHOLD = 0.18         # 정면 대비 코가 눈 사이 거리의 18% 이상 옆으로 가면 고개를 돌린 것
CENTER_YAW = 0.12             # 정면으로 돌아왔다고 볼 각도 범위
MOTIONS = ("TURN LEFT", "TURN RIGHT", "MOVE CLOSER")
WINDOW_SIZE = guide_view.CANVAS_SIZE   # 왼쪽 카메라 + 오른쪽 단계 안내 (10-B)


class OpenCVFace:
    """한 명의 주장된 회원을 1:1로 확인하는 얼굴 인증 공급자."""

    def __init__(self, vault, camera_index: int = 0):
        self.vault = vault
        self.camera_index = camera_index
        self.detector_path = config.FACE_DETECTOR_PATH
        self.recognizer_path = config.FACE_RECOGNIZER_PATH
        self._check_models()
        self.detector = cv2.FaceDetectorYN.create(
            "ONNX", self.detector_path.read_bytes(), b"", (320, 240), 0.9, 0.3, 5000
        )
        self.recognizer = cv2.FaceRecognizerSF.create(
            "ONNX", self.recognizer_path.read_bytes(), b""
        )

    def _check_models(self) -> None:
        required = (
            (self.detector_path, config.FACE_DETECTOR_SHA256),
            (self.recognizer_path, config.FACE_RECOGNIZER_SHA256),
        )
        for path, expected in required:
            path = Path(path)
            if not path.exists():
                raise FaceError(f"얼굴 인식 모델이 없습니다: {path.name}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
            if actual != expected.lower():
                raise FaceError(f"얼굴 인식 모델 무결성 검사 실패: {path.name}")

    def camera_available(self) -> bool:
        cap = self._open_camera()
        try:
            ok, frame = cap.read()
            return bool(ok and frame is not None and frame.size)
        finally:
            cap.release()

    def enroll_face(self, customer_id, on_status=print) -> bool:
        on_status("카메라를 열어 무작위 동작 확인 후 얼굴 특징을 등록합니다")
        feature = self._capture_live_feature("ENROLL", on_status)
        profiles = self.vault.read("face_profiles", default={})
        profiles[customer_id] = {
            "customer_id": customer_id,
            "algorithm": "OpenCV-SFace-2021dec",
            "feature": feature.astype(float).reshape(-1).tolist(),
            "created_at": now_iso(),
            "liveness": "random-two-motion-v2-yaw",
        }
        self.vault.write("face_profiles", profiles)
        on_status("얼굴 등록 완료 · 원본 사진은 저장하지 않았습니다")
        return True

    def identify_face(self, claimed_customer_id, on_status=print):
        profile = self.vault.read("face_profiles", default={}).get(claimed_customer_id)
        if not profile:
            raise FaceError("등록된 얼굴 특징이 없습니다. 얼굴을 먼저 등록하거나 비밀번호를 사용하세요")
        on_status("무작위 동작으로 실제 사람인지 확인한 뒤 얼굴을 비교합니다")
        probe = self._capture_live_feature("LOGIN", on_status)
        stored = np.asarray(profile["feature"], dtype=np.float32).reshape(1, -1)
        score = float(self.recognizer.match(
            stored, probe.reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE
        ))
        on_status(f"얼굴 유사도 검사 완료 ({score:.3f})")
        return claimed_customer_id if score >= COSINE_THRESHOLD else None

    def verify_face(self, on_status=print) -> bool:
        self._capture_live_feature("VERIFY", on_status)
        return True

    def _open_camera(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            raise FaceError(
                f"카메라 {self.camera_index}번을 열 수 없습니다. 다른 앱을 닫고 비밀번호 로그인을 사용하세요"
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return cap

    def _detect_one(self, frame):
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _result, faces = self.detector.detect(frame)
        if faces is None or len(faces) != 1:
            return None, 0 if faces is None else len(faces)
        return faces[0], 1

    @staticmethod
    def _yaw(face) -> float:
        """눈 두 개 가운데에서 코가 얼마나 옆으로 갔는지 (눈 사이 거리 기준). 정면이면 0 근처.

        YuNet 결과: [x, y, w, h, 눈1 x, y, 눈2 x, y, 코 x, y, 입꼬리1 x, y, 입꼬리2 x, y, 점수].
        거울 화면 기준으로 사용자가 자기 왼쪽으로 고개를 돌리면 값이 음수가 된다.
        """
        if len(face) < 10:
            return 0.0
        e1x, e2x, nose_x = float(face[4]), float(face[6]), float(face[8])
        eye_dist = max(abs(e1x - e2x), 1.0)
        return (nose_x - (e1x + e2x) / 2) / eye_dist

    @classmethod
    def _pose(cls, face) -> tuple:
        """기준 자세로 모을 값: 얼굴 박스 4개 + 좌우 각도."""
        return (*map(float, face[:4]), cls._yaw(face))

    @classmethod
    def _passed(cls, challenge: str, face, baseline) -> bool:
        _x, _y, w, h = map(float, face[:4])
        _bx, _by, bw, bh, base_yaw = baseline
        yaw = cls._yaw(face)
        if challenge == "TURN LEFT":
            return yaw < base_yaw - TURN_THRESHOLD
        if challenge == "TURN RIGHT":
            return yaw > base_yaw + TURN_THRESHOLD
        if challenge == "MOVE CLOSER":
            return w * h > bw * bh * 1.35
        return False

    @classmethod
    def _centered(cls, face, baseline) -> bool:
        x, _y, w, h = map(float, face[:4])
        bx, _by, bw, bh, base_yaw = baseline
        return (
            abs((x + w / 2) - (bx + bw / 2)) < max(45.0, bw * 0.28)
            and 0.72 < (w * h) / (bw * bh) < 1.38
            and abs(cls._yaw(face) - base_yaw) < CENTER_YAW
        )

    def _feature(self, frame, face) -> np.ndarray:
        aligned = self.recognizer.alignCrop(frame, face)
        feature = self.recognizer.feature(aligned).astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(feature))
        if norm == 0:
            raise FaceError("얼굴 특징을 만들지 못했습니다")
        return feature / norm

    def _capture_live_feature(self, purpose: str, on_status) -> np.ndarray:
        cap = self._open_camera()
        title = "BONGMIN KIOSK - Face check (ESC: cancel)"
        # 등록은 한 번뿐이라 동작 2개, 로그인은 빠르게 1개 (아이폰처럼 정면 위주).
        enrolling = purpose == "ENROLL"
        challenges = random.sample(MOTIONS, 2 if enrolling else 1)
        needed_samples = CAPTURE_SAMPLES if enrolling else LOGIN_SAMPLES
        calibration_frames = 18 if enrolling else 12
        calibration = []
        stable_hits = 0
        step = 0
        return_hits = 0
        samples = []
        frame_no = 0
        started = time.monotonic()
        on_status("카메라 창에서 얼굴을 정면으로 맞춰 주세요. ESC로 취소할 수 있습니다")
        cv2.namedWindow(title, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(title, *WINDOW_SIZE)
        try:
            cv2.setWindowProperty(title, cv2.WND_PROP_TOPMOST, 1)
        except cv2.error:
            pass
        try:
            while time.monotonic() - started < SESSION_SECONDS:
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise FaceError("카메라 영상을 읽지 못했습니다")
                # 거울처럼 좌우를 뒤집는다. 등록과 로그인 모두 같은 방식이라 비교 결과는 같다.
                frame = cv2.flip(frame, 1)
                frame_no += 1
                face, count = self._detect_one(frame)
                motion_ok = False

                if face is not None:
                    if len(calibration) < calibration_frames:
                        # 얼굴이 ROI 타원 안에 있을 때만 기준 자세로 모은다.
                        if guide_view.frame_in_roi(frame, face):
                            calibration.append(self._pose(face))
                    else:
                        baseline = tuple(np.median(np.asarray(calibration), axis=0))
                        if step < len(challenges):
                            motion_ok = self._passed(challenges[step], face, baseline)
                            if motion_ok:
                                stable_hits += 1
                                if stable_hits >= 4:
                                    step += 1
                                    stable_hits = 0
                                    on_status(f"동작 {step}/{len(challenges)} 확인 완료")
                            else:
                                stable_hits = max(0, stable_hits - 1)
                        else:
                            if self._centered(face, baseline):
                                return_hits += 1
                                if return_hits >= 5 and frame_no % 3 == 0:
                                    samples.append(self._feature(frame, face))
                            else:
                                return_hits = 0
                            if len(samples) >= needed_samples:
                                mean = np.mean(np.vstack(samples), axis=0).astype(np.float32)
                                mean /= np.linalg.norm(mean)
                                return mean

                progress = (len(calibration) / calibration_frames * 0.3 + step / len(challenges) * 0.4
                            + len(samples) / needed_samples * 0.3)
                display = guide_view.compose(frame, face, count, challenges,
                                             len(calibration) >= calibration_frames,
                                             step, purpose, progress, motion_ok)
                cv2.imshow(title, display)
                if cv2.waitKey(1) & 0xFF == 27:
                    raise FaceError("사용자가 얼굴 인증을 취소했습니다")
        finally:
            cap.release()
            cv2.destroyAllWindows()
        raise FaceError("제한 시간 안에 생체 확인을 완료하지 못했습니다. 조명을 확인하고 다시 시도하세요")
