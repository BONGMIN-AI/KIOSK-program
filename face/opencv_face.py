"""로컬 얼굴 등록·로그인 (10/29 교체: YuNet 검출 + ArcFace 비교 + MiniFASNet 사진 판정).

얼굴 인증 세부 흐름 (docs/FACE_AUTH_FLOW.md):
  F1 카메라 → F2 50cm 안 얼굴 한 명 → F3 가림(마스크·선글라스·모자챙) → F4 품질(거리·정면·밝기·흔들림)
  → F5 진짜 사람(MiniFASNet, D435가 있으면 깊이도) → F6 여러 장 비교 + 다른 회원과 비교

고개 동작은 없다. 정면을 보고 잠깐 멈추면 된다.
사진과 영상 프레임은 저장하지 않는다. ArcFace가 만든 512개 숫자만 Vault의 ``face_profiles``에
암호화해 저장한다. 깊이 영상과 측정값도 저장하지 않고 통과/거절만 쓴다.

수업용 수준이다. 정교한 3D 마스크·고화질 영상까지 막는 상용 위조 방지 시스템은 아니다.
"""
from __future__ import annotations

import functools
import hashlib
import os
import time
from pathlib import Path

import cv2
import numpy as np

import config
from core.schema import now_iso
from . import FaceError, SpoofError, guide_view, quality
from .depth_check import DepthVote, RealSenseCamera, judge, realsense_available, sample_depth
from .engines import AntiSpoof, ArcFace

ALGORITHM = "ArcFace-w600k_r50"
# 얼굴 유사도 기준 (ArcFace 코사인). 공개 사진 시험에서 같은 사람 0.9 이상, 다른 사람 0.05 안팎.
# 웹캠은 조명 때문에 같은 사람도 0.5~0.8 정도라 0.45로 둔다. 현장에서는 KIOSK_FACE_THRESHOLD로 바꾼다.
DEFAULT_COSINE_THRESHOLD = 0.45
MIN_PASSING_SAMPLES = 4        # 로그인 5장 중 4장 이상이 기준을 넘어야 한다 (우연히 한 장 통과 방지)
ENROLL_CONSISTENCY = 0.6       # 등록 10장이 서로 이만큼은 닮아야 한다 (흔들린 등록 방지)
SESSION_SECONDS = 30
CAPTURE_SAMPLES = 10           # 등록: 정면 특징 10장 평균
LOGIN_SAMPLES = 5              # 로그인·확인: 5장
WINDOW_SIZE = guide_view.CANVAS_SIZE   # 왼쪽 카메라 + 오른쪽 단계 안내 (10-B)
LIVE_CHALLENGE = "LIVE CHECK"
DEPTH_CHALLENGE = "DEPTH CHECK"
SPOOF_GIVE_UP_FRAMES = 60      # 진짜 얼굴 판정이 계속 실패하면(약 2초) 사진·화면으로 보고 멈춘다
COVERED_GIVE_UP_FRAMES = 90    # 마스크·선글라스가 약 3초 계속 보이면 안내하고 멈춘다
# 뒤에 지나가는 사람은 무시하고 키오스크 앞 약 50cm 안의 얼굴만 쓴다.
NEAR_DISTANCE_M = 0.55         # D435: 코까지 거리
NEAR_FACE_WIDTH = 120          # 웹캠(640x480): 얼굴 폭이 이보다 작으면 50~60cm보다 멀다
FAR_ALERT = "카메라 앞 50cm 안으로 와 주세요"
ANTISPOOF_MODELS = (           # (모델, 얼굴 박스를 넓히는 배수)
    (config.FACE_ANTISPOOF_V2_PATH, 2.7),
    (config.FACE_ANTISPOOF_V1SE_PATH, 4.0),
)


def depth_wanted() -> bool:
    """D435를 쓸지: 환경변수 KIOSK_DEPTH=0이면 끄고, 아니면 연결돼 있을 때 쓴다."""
    return os.environ.get("KIOSK_DEPTH", "1") != "0" and realsense_available()


def cosine_threshold() -> float:
    """얼굴 유사도 기준값: 환경변수 KIOSK_FACE_THRESHOLD가 있으면 그 값, 없으면 기본값."""
    try:
        return float(os.environ.get("KIOSK_FACE_THRESHOLD", DEFAULT_COSINE_THRESHOLD))
    except ValueError:
        return DEFAULT_COSINE_THRESHOLD


def judge_login(samples, stored, others, threshold):
    """F6: 로그인 사진 여러 장을 저장된 얼굴과 비교한다. (통과 여부, 안내 문구)를 돌려준다.

    samples: (n, 512) 로그인 특징, stored: (512,) 이 회원 특징, others: {다른 ID: (512,)}.
    """
    scores = samples @ stored
    mean = float(scores.mean())
    passing = int((scores >= threshold).sum())
    needed = min(MIN_PASSING_SAMPLES, len(scores))
    text = f"얼굴 유사도 {mean:.3f} (기준 {threshold:.2f}, {passing}/{len(scores)}장 통과)"
    if passing < needed or mean < threshold:
        return False, text
    probe = samples.mean(axis=0)
    probe /= np.linalg.norm(probe)
    rival = max((float(probe @ vector) for vector in others.values()), default=-1.0)
    if rival >= float(probe @ stored):
        return False, f"{text} · 다른 등록 얼굴과 더 닮았어요 ({rival:.3f})"
    return True, text


def check_models() -> None:
    for path, expected in config.FACE_MODELS:
        path = Path(path)
        if not path.exists():
            raise FaceError(f"얼굴 인식 모델이 없습니다: {path.name} (tools/get_face_models.py 실행)")
        actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
        if actual != expected.lower():
            raise FaceError(f"얼굴 인식 모델 무결성 검사 실패: {path.name}")


@functools.cache
def load_models():
    """모델 검사·불러오기는 처음 한 번만 한다 (ArcFace는 170MB라 매번 읽으면 느리다)."""
    check_models()
    detector = cv2.FaceDetectorYN.create(
        "ONNX", config.FACE_DETECTOR_PATH.read_bytes(), b"", (320, 240), 0.9, 0.3, 5000
    )
    try:
        return detector, ArcFace(config.FACE_ARCFACE_PATH), AntiSpoof(ANTISPOOF_MODELS)
    except ImportError as exc:
        raise FaceError("onnxruntime이 없습니다. requirements.txt를 다시 설치하세요") from exc


class OpenCVFace:
    """한 명의 주장된 회원을 1:1로 확인하는 얼굴 인증 공급자."""

    def __init__(self, vault, camera_index: int = 0, use_depth: bool | None = None):
        self.vault = vault
        self.camera_index = camera_index
        self.use_depth = depth_wanted() if use_depth is None else use_depth
        # 키오스크 창 안에 카메라 화면을 그리는 함수 (image, 기다릴 ms) -> 취소했으면 True.
        # 없으면 OpenCV 창을 따로 띄운다 (터미널 앱·시험용).
        self.viewer = None
        # 프레임마다 손님에게 보여 줄 짧은 안내 한 줄 (text) -> None. 로그인 화면이 오른쪽 칸에 띄운다.
        self.on_step = None
        self.detector, self.recognizer, self.antispoof = load_models()

    def camera_available(self) -> bool:
        cap = self._open_camera()
        try:
            ok, frame = cap.read()
            return bool(ok and frame is not None and frame.size)
        finally:
            cap.release()

    def enroll_face(self, customer_id, on_status=print) -> bool:
        on_status("정면을 보고 잠시 멈추면 얼굴 특징을 등록합니다")
        samples = self._capture_samples("ENROLL", on_status)
        feature = samples.mean(axis=0)
        feature /= np.linalg.norm(feature)
        if float((samples @ feature).min()) < ENROLL_CONSISTENCY:
            raise FaceError("등록하는 동안 얼굴이 많이 달라졌어요. 정면을 본 채 다시 시도해 주세요")
        profiles = self.vault.read("face_profiles", default={})
        profiles[customer_id] = {
            "customer_id": customer_id,
            "algorithm": ALGORITHM,
            "feature": feature.astype(float).tolist(),
            "created_at": now_iso(),
            "liveness": "minifasnet+d435-depth" if self.use_depth else "minifasnet",
        }
        self.vault.write("face_profiles", profiles)
        on_status("얼굴 등록 완료 · 원본 사진은 저장하지 않았습니다")
        return True

    def identify_face(self, claimed_customer_id, on_status=print):
        profiles = self.vault.read("face_profiles", default={})
        profile = profiles.get(claimed_customer_id)
        if not profile:
            raise FaceError("등록된 얼굴 특징이 없습니다. 얼굴을 먼저 등록하거나 비밀번호를 사용하세요")
        if profile.get("algorithm") != ALGORITHM:
            raise FaceError("얼굴 인식 방식이 바뀌어 얼굴을 다시 등록해야 해요. "
                            "비밀번호로 확인한 뒤 얼굴을 다시 등록해 주세요")
        on_status("정면을 보고 잠시 멈춰 주세요")
        samples = self._capture_samples("LOGIN", on_status)
        others = {key: np.asarray(item["feature"], dtype=np.float32) for key, item in profiles.items()
                  if key != claimed_customer_id and item.get("algorithm") == ALGORITHM}
        passed, text = judge_login(samples, np.asarray(profile["feature"], dtype=np.float32),
                                   others, cosine_threshold())
        on_status(text)
        return claimed_customer_id if passed else None

    def verify_face(self, on_status=print) -> bool:
        self._capture_samples("VERIFY", on_status)
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

    def _detect_one(self, frame, depth=None):
        """F2: 가까운 얼굴 하나. (얼굴 또는 None, 가까운 얼굴 수, 멀리만 사람이 있는지)."""
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _result, faces = self.detector.detect(frame)
        faces = [] if faces is None else list(faces)
        near = [face for face in faces if self._near(face, depth)]
        if len(near) == 1:
            return near[0], 1, False
        return None, len(near), bool(faces) and not near

    @staticmethod
    def _near(face, depth) -> bool:
        if depth is not None:
            distance = sample_depth(depth, face[8], face[9])          # 코끝까지 거리 (m)
            return distance is not None and distance <= NEAR_DISTANCE_M
        return float(face[2]) >= NEAR_FACE_WIDTH

    def _capture_samples(self, purpose: str, on_status) -> np.ndarray:
        """F1~F5를 지나 정면 얼굴 특징 여러 장을 (n, 512)로 돌려준다."""
        title = "COFFEE & SPOON KIOSK - Face check (ESC: cancel)"
        enrolling = purpose == "ENROLL"
        challenges = [DEPTH_CHALLENGE if self.use_depth else LIVE_CHALLENGE]
        depth_camera, cap = None, None
        if self.use_depth:
            depth_camera = RealSenseCamera().__enter__()
        else:
            cap = self._open_camera()
        live_vote = DepthVote()
        spoof_fails = 0
        covered_frames = 0
        needed_samples = CAPTURE_SAMPLES if enrolling else LOGIN_SAMPLES
        settle_frames = 10 if enrolling else 3
        settled = 0
        step = 0
        samples = []
        last_alert = ""
        started = time.monotonic()
        on_status("카메라 화면에서 얼굴을 정면으로 맞춰 주세요. ESC로 취소할 수 있습니다")
        if self.viewer is None:
            cv2.namedWindow(title, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(title, *WINDOW_SIZE)
            try:
                cv2.setWindowProperty(title, cv2.WND_PROP_TOPMOST, 1)
            except cv2.error:
                pass
        try:
            while time.monotonic() - started < SESSION_SECONDS:
                depth = None
                if depth_camera is not None:
                    frame, depth = depth_camera.read()      # 이미 거울처럼 뒤집혀 있다
                    ok = frame is not None
                else:
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        # 거울처럼 좌우를 뒤집는다. 등록과 로그인 모두 같은 방식이라 비교 결과는 같다.
                        frame = cv2.flip(frame, 1)
                if not ok or frame is None:
                    raise FaceError("카메라 영상을 읽지 못했습니다")
                face, count, far = self._detect_one(frame, depth)    # F2: 가까운 얼굴 한 명
                alert = FAR_ALERT if far else ""
                live_ok = False
                if face is not None:
                    alert = quality.check(frame, face)       # F3 가림 · F4 품질
                    covered_frames = covered_frames + 1 if alert in quality.COVERED else 0
                    if covered_frames >= COVERED_GIVE_UP_FRAMES:
                        raise FaceError(f"{alert} 다시 시도하거나 비밀번호를 사용하세요")
                if face is not None and not alert:
                    last_alert = ""
                    if settled < settle_frames:
                        settled += 1
                    else:
                        # F5 진짜 사람 판정과 F6용 특징 모으기를 같은 프레임에서 함께 한다 (빠르게).
                        # '진짜'로 나온 프레임의 얼굴만 비교에 쓴다.
                        live_ok = self.antispoof.is_real(frame, face)
                        if depth is not None:
                            live_ok = live_ok and judge(depth, face).ok
                        live_vote.add(live_ok)
                        spoof_fails = 0 if live_ok else spoof_fails + 1
                        if spoof_fails >= SPOOF_GIVE_UP_FRAMES:
                            raise SpoofError("진짜 얼굴이 확인되지 않았어요 (사진·화면으로 보여요). "
                                             "비밀번호로 로그인하세요")
                        if step < len(challenges) and live_vote.passed:
                            step += 1
                            on_status("진짜 얼굴 확인 완료")
                        if live_ok and len(samples) < needed_samples:
                            samples.append(self.recognizer.feature(frame, face))
                        if step >= len(challenges) and len(samples) >= needed_samples:
                            if not enrolling:   # 얼굴 기호가 초록 체크로 바뀐 뒤 잠깐 있다가 사라진다
                                self._show(title, guide_view.compose(
                                    frame, face, count, challenges, True, len(challenges),
                                    purpose, 1.0, True, done=True), 600)
                            return np.vstack(samples)
                elif alert:
                    last_alert = alert

                progress = (settled / settle_frames * 0.2 + step / len(challenges) * 0.3
                            + len(samples) / needed_samples * 0.5)
                if self.on_step is not None:
                    self.on_step(self.step_text(face, count, alert, settled >= settle_frames, step < len(challenges)))
                display = guide_view.compose(frame, face, count, challenges, settled >= settle_frames,
                                             step, purpose, progress, live_ok, alert=alert)
                if self._show(title, display, 1):
                    raise FaceError("사용자가 얼굴 인증을 취소했습니다")
        finally:
            if cap is not None:
                cap.release()
            if depth_camera is not None:
                depth_camera.__exit__(None, None, None)
            if self.viewer is None:
                cv2.destroyAllWindows()
        reason = f"{last_alert} " if last_alert else ""
        raise FaceError(f"{reason}제한 시간 안에 얼굴 확인을 끝내지 못했어요. 다시 시도하거나 비밀번호를 사용하세요")

    @staticmethod
    def step_text(face, count, alert, settled, checking) -> str:
        """지금 손님이 할 일 한 줄 ('입체 확인' 같은 기술 말은 쓰지 않는다)."""
        if alert:
            return alert
        if face is None:
            return "한 사람만 카메라 앞에 서 주세요" if count > 1 else "카메라 앞에 서 주세요"
        if not settled:
            return "카메라를 바라봐 주세요"
        if checking:
            return "정면을 보고 잠시 멈춰 주세요"
        return "확인하고 있어요…"

    def _show(self, title, image, wait_ms) -> bool:
        """카메라 안내 화면 한 장을 보여 준다. 취소(ESC·취소 버튼)했으면 True."""
        if self.viewer is not None:
            return bool(self.viewer(image, wait_ms))
        cv2.imshow(title, image)
        return cv2.waitKey(wait_ms) & 0xFF == 27
