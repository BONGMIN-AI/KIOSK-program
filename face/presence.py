"""사람 감지 (11/02 C묶음): 대기 화면 접근 감지(1m) · 주문 중 자리 비움 감지.

카메라를 뒤에서 계속 읽어 '가장 가까운 사람까지 거리(m)'만 남긴다. 영상·거리 기록은 저장하지 않는다.
- D435가 있으면 얼굴 코끝 깊이. 얼굴이 안 보여도(고개 숙임) 화면 가운데 깊이가 가까우면 사람이 있는 것으로 본다.
- 웹캠만 있으면 얼굴 폭으로 거리를 어림한다 (640x480에서 폭 120px ≈ 55cm).

얼굴 로그인·스마일 할인이 카메라를 쓰는 동안에는 pause()로 카메라를 놓아 준다.
"""
from __future__ import annotations

import os
import threading
import time

import numpy as np

FACE_WIDTH_AT_1M = 66          # 웹캠 얼굴 폭(px) × 거리(m) ≈ 66
BODY_DEPTH_M = 1.2             # D435: 화면 가운데가 이보다 가까우면 얼굴이 안 보여도 사람이 있다
POLL_SECONDS = 0.25


def face_distance(face_width_px: float) -> float:
    """웹캠 얼굴 폭으로 어림한 거리(m)."""
    return FACE_WIDTH_AT_1M / max(face_width_px, 1.0)


def presence_wanted() -> bool:
    """환경변수 KIOSK_PRESENCE=off이면 끈다 (자동 테스트·카메라 없는 PC)."""
    return os.environ.get("KIOSK_PRESENCE", "on").lower() not in ("off", "0", "no")


class FakePresence:
    """자동 테스트용: distance를 직접 넣는다 (None = 아무도 없음)."""

    def __init__(self, distance=None):
        self.distance = distance
        self.paused = False

    def latest(self):
        return self.distance

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        pass


class CameraPresence:
    """뒤쪽 스레드에서 카메라를 읽어 가장 가까운 사람까지 거리를 latest()로 알려 준다."""

    def __init__(self, camera_index: int = 0, use_depth: bool | None = None):
        self.camera_index = camera_index
        self.use_depth = use_depth
        self.distance = None
        self.working = True                 # 카메라를 못 열면 False (화면은 평소처럼 터치로만)
        self._want_pause = threading.Event()
        self._released = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="presence", daemon=True)
        self._thread.start()

    def latest(self):
        return self.distance if self.working else None

    def pause(self, wait: float = 3.0):
        """카메라를 놓을 때까지 기다린다 (얼굴 로그인이 같은 카메라를 연다)."""
        self._released.clear()
        self._want_pause.set()
        if self._thread.is_alive():
            self._released.wait(wait)
        self.distance = None

    def resume(self):
        self._want_pause.clear()

    def stop(self):
        self._stop.set()
        self._want_pause.set()
        self._thread.join(2)

    def _run(self):
        try:
            import cv2
            import config
            from .depth_check import RealSenseCamera, realsense_available, sample_depth
            detector = cv2.FaceDetectorYN.create(
                "ONNX", config.FACE_DETECTOR_PATH.read_bytes(), b"", (320, 240), 0.8, 0.3, 5000)
        except Exception:                    # 모델·모듈이 없으면 감지 없이 돈다
            self.working = False
            self._released.set()
            return
        use_depth = self.use_depth
        if use_depth is None:
            use_depth = os.environ.get("KIOSK_DEPTH", "1") != "0" and realsense_available()
        while not self._stop.is_set():
            if self._want_pause.is_set():
                self._released.set()
                time.sleep(POLL_SECONDS)
                continue
            try:
                if use_depth:
                    camera = RealSenseCamera().__enter__()
                    read = camera.read
                    close = lambda: camera.__exit__(None, None, None)
                else:
                    cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        cap.release()
                        raise OSError("camera")
                    read = lambda: (cap.read()[1], None)
                    close = cap.release
            except Exception:
                self.working = False
                self._released.set()
                return
            try:
                while not self._stop.is_set() and not self._want_pause.is_set():
                    frame, depth = read()
                    if frame is None:
                        break
                    self.distance = self._measure(cv2, detector, frame, depth, sample_depth)
                    time.sleep(POLL_SECONDS)
            except Exception:
                self.distance = None
            finally:
                close()
                self._released.set()

    @staticmethod
    def _measure(cv2, detector, frame, depth, sample_depth):
        height, width = frame.shape[:2]
        detector.setInputSize((width, height))
        _ok, faces = detector.detect(frame)
        faces = [] if faces is None else list(faces)
        distances = []
        for face in faces:
            if depth is not None:
                value = sample_depth(depth, face[8], face[9])
                if value is not None:
                    distances.append(value)
            else:
                distances.append(face_distance(face[2] * 640 / width))
        if not distances and depth is not None:
            middle = depth[height // 3: height * 2 // 3, width // 3: width * 2 // 3]
            valid = middle[middle > 0.1]
            if valid.size > middle.size // 4:
                body = float(np.median(valid))
                if body <= BODY_DEPTH_M:
                    distances.append(body)
        return min(distances) if distances else None
