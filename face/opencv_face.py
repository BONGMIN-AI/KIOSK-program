"""OpenCV YuNet + SFace 기반 로컬 얼굴 등록·로그인.

사진과 영상 프레임은 저장하지 않는다. SFace가 만든 128차원 특징값만 기존
Vault의 ``face_profiles`` 데이터셋에 저장하므로 디스크에서는 암호화된다.
로그인 때마다 무작위 움직임 두 가지를 요구해 정지 사진 공격을 줄인다.

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
from . import FaceError


COSINE_THRESHOLD = 0.363
SESSION_SECONDS = 45
CAPTURE_SAMPLES = 10
WINDOW_SIZE = (960, 720)   # 카메라 창을 크게 띄워 자기 얼굴 방향을 보면서 따라 할 수 있게 한다


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
            "liveness": "random-two-motion-v1",
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
    def _passed(challenge: str, face, baseline) -> bool:
        x, _y, w, h = map(float, face[:4])
        bx, _by, bw, bh = baseline
        cx, base_cx = x + w / 2, bx + bw / 2
        if challenge == "MOVE LEFT":
            return cx < base_cx - max(35.0, bw * 0.22)
        if challenge == "MOVE RIGHT":
            return cx > base_cx + max(35.0, bw * 0.22)
        if challenge == "MOVE CLOSER":
            return w * h > bw * bh * 1.35
        return False

    @staticmethod
    def _centered(face, baseline) -> bool:
        x, _y, w, h = map(float, face[:4])
        bx, _by, bw, bh = baseline
        return (
            abs((x + w / 2) - (bx + bw / 2)) < max(45.0, bw * 0.28)
            and 0.72 < (w * h) / (bw * bh) < 1.38
        )

    def _feature(self, frame, face) -> np.ndarray:
        aligned = self.recognizer.alignCrop(frame, face)
        feature = self.recognizer.feature(aligned).astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(feature))
        if norm == 0:
            raise FaceError("얼굴 특징을 만들지 못했습니다")
        return feature / norm

    @staticmethod
    def _draw_guide(display, prompt: str, color, detail: str, purpose: str, progress: float) -> None:
        """가운데 얼굴 안내선, 방향 화살표, 진행 막대를 그린다. (OpenCV 글꼴은 영어만 쓴다)"""
        h, w = display.shape[:2]
        cx, cy = w // 2, h // 2 + 10
        cv2.ellipse(display, (cx, cy), (w // 6, h // 4), 0, 0, 360, (255, 255, 255), 2, cv2.LINE_AA)
        arrow = {"MOVE LEFT": ((cx - 40, cy), (cx - w // 3, cy)),
                 "MOVE RIGHT": ((cx + 40, cy), (cx + w // 3, cy))}.get(prompt)
        if arrow:
            cv2.arrowedLine(display, arrow[0], arrow[1], (0, 220, 255), 8, cv2.LINE_AA, tipLength=0.25)
        elif prompt == "MOVE CLOSER":
            cv2.ellipse(display, (cx, cy), (w // 4, h // 3), 0, 0, 360, (0, 220, 255), 4, cv2.LINE_AA)
        cv2.rectangle(display, (0, 0), (w, 84), (20, 20, 20), -1)
        cv2.putText(display, prompt, (18, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3, cv2.LINE_AA)
        cv2.putText(display, f"{purpose} | {detail} | ESC: cancel", (18, 72),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)
        bar_w = int((w - 36) * max(0.0, min(1.0, progress)))
        cv2.rectangle(display, (18, h - 30), (w - 18, h - 14), (60, 60, 60), -1)
        cv2.rectangle(display, (18, h - 30), (18 + bar_w, h - 14), (70, 220, 70), -1)

    def _capture_live_feature(self, purpose: str, on_status) -> np.ndarray:
        cap = self._open_camera()
        title = "BONGMIN KIOSK - Face check (ESC: cancel)"
        challenges = random.sample(["MOVE LEFT", "MOVE RIGHT", "MOVE CLOSER"], 2)
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
                display = frame.copy()
                prompt = "LOOK CENTER"
                detail = "Keep exactly one face in the box"
                color = (0, 200, 255)

                if face is not None:
                    x, y, w, h = face[:4].astype(int)
                    cv2.rectangle(display, (x, y), (x + w, y + h), (70, 220, 70), 2)
                    if len(calibration) < 18:
                        calibration.append(tuple(map(float, face[:4])))
                        detail = f"Calibrating {len(calibration)}/18"
                    else:
                        baseline = tuple(np.median(np.asarray(calibration), axis=0))
                        if step < len(challenges):
                            prompt = challenges[step]
                            detail = f"Random liveness {step + 1}/{len(challenges)}"
                            if self._passed(prompt, face, baseline):
                                stable_hits += 1
                                if stable_hits >= 4:
                                    step += 1
                                    stable_hits = 0
                                    on_status(f"동작 {step}/2 확인 완료")
                            else:
                                stable_hits = max(0, stable_hits - 1)
                        else:
                            prompt = "RETURN TO CENTER"
                            detail = "Capturing encrypted face features"
                            if self._centered(face, baseline):
                                return_hits += 1
                                if return_hits >= 5 and frame_no % 3 == 0:
                                    samples.append(self._feature(frame, face))
                            else:
                                return_hits = 0
                            if len(samples) >= CAPTURE_SAMPLES:
                                mean = np.mean(np.vstack(samples), axis=0).astype(np.float32)
                                mean /= np.linalg.norm(mean)
                                return mean
                else:
                    if count > 1:
                        prompt, detail = "ONE PERSON ONLY", "Multiple faces detected"
                    else:
                        prompt, detail = "FACE NOT FOUND", "Move into the camera view"
                    color = (0, 0, 255)

                progress = (len(calibration) / 18 * 0.3 + step / len(challenges) * 0.4
                            + len(samples) / CAPTURE_SAMPLES * 0.3)
                self._draw_guide(display, prompt, color, detail, purpose, progress)
                cv2.imshow(title, display)
                if cv2.waitKey(1) & 0xFF == 27:
                    raise FaceError("사용자가 얼굴 인증을 취소했습니다")
        finally:
            cap.release()
            cv2.destroyAllWindows()
        raise FaceError("제한 시간 안에 생체 확인을 완료하지 못했습니다. 조명을 확인하고 다시 시도하세요")
