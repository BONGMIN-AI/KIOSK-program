"""Intel RealSense 깊이 영상으로 '입체 얼굴'인지 확인한다 (사진·휴대폰 화면 거절).

판정 방법
- YuNet이 찾은 눈 2개·입꼬리 2개의 깊이로 얼굴 평면을 하나 만든다.
- 코끝이 그 평면보다 카메라 쪽으로 몇 mm 나와 있는지(코 돌출) 잰다.
- 진짜 얼굴은 보통 15~30mm, 사진·화면은 기울여 들어도 평평해서 0 근처다.

깊이 영상과 측정값은 저장하지 않는다. 그 자리에서 통과/거절만 판정하고 버린다.
GUI와 합치기 전 단계의 기능 모듈이며, 화면 표시는 tools/depth_face_test.py가 맡는다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_NOSE_MM = 8.0          # 이보다 덜 나오면 평평한 것(사진·화면)으로 본다
MAX_NOSE_MM = 70.0         # 이보다 크면 측정 오류로 본다
MIN_DIST_M, MAX_DIST_M = 0.25, 1.2   # D435가 얼굴 깊이를 안정적으로 재는 거리
PATCH = 3                  # 점 주변 (2*PATCH+1)^2 칸의 중앙값을 쓴다

# YuNet 결과에서 점 위치: 눈1, 눈2, 코, 입꼬리1, 입꼬리2
EYE1, EYE2, NOSE, MOUTH1, MOUTH2 = (4, 5), (6, 7), (8, 9), (10, 11), (12, 13)


@dataclass
class DepthResult:
    ok: bool
    reason: str
    nose_mm: float | None = None
    distance_m: float | None = None


def sample_depth(depth_m, x: float, y: float, patch: int = PATCH):
    """(x, y) 주변의 유효한 깊이(미터) 중앙값. 측정값이 너무 적으면 None."""
    h, w = depth_m.shape[:2]
    xi, yi = int(round(x)), int(round(y))
    if not (0 <= xi < w and 0 <= yi < h):
        return None
    window = depth_m[max(0, yi - patch):yi + patch + 1, max(0, xi - patch):xi + patch + 1]
    valid = window[window > 0]
    if valid.size < max(3, window.size // 3):
        return None
    return float(np.median(valid))


def nose_protrusion_mm(depth_m, face):
    """눈·입꼬리 4점으로 만든 평면보다 코끝이 카메라 쪽으로 나온 거리(mm)와 얼굴까지 거리(m)."""
    if len(face) < 14:
        return None, None
    pts = []
    for ix, iy in (EYE1, EYE2, MOUTH1, MOUTH2):
        z = sample_depth(depth_m, face[ix], face[iy])
        if z is None:
            return None, None
        pts.append((float(face[ix]), float(face[iy]), z))
    nose_z = sample_depth(depth_m, face[NOSE[0]], face[NOSE[1]])
    if nose_z is None:
        return None, None
    a = np.array([[x, y, 1.0] for x, y, _ in pts])
    b = np.array([z for _, _, z in pts])
    coef, *_ = np.linalg.lstsq(a, b, rcond=None)          # z = c0*x + c1*y + c2
    plane_z = coef[0] * face[NOSE[0]] + coef[1] * face[NOSE[1]] + coef[2]
    return (plane_z - nose_z) * 1000.0, float(np.mean(b))


def judge(depth_m, face) -> DepthResult:
    """한 프레임 판정."""
    nose_mm, dist = nose_protrusion_mm(depth_m, face)
    if nose_mm is None:
        return DepthResult(False, "깊이를 재지 못했어요 (너무 가깝거나 빛 반사)")
    if not (MIN_DIST_M <= dist <= MAX_DIST_M):
        return DepthResult(False, f"거리 {dist:.2f}m · 25cm~1.2m 사이로 와 주세요", nose_mm, dist)
    if nose_mm < MIN_NOSE_MM:
        return DepthResult(False, "평평해요 · 사진이나 화면으로 보여요", nose_mm, dist)
    if nose_mm > MAX_NOSE_MM:
        return DepthResult(False, "깊이 값이 이상해요 · 다시 시도", nose_mm, dist)
    return DepthResult(True, "입체 얼굴 확인", nose_mm, dist)


class DepthVote:
    """여러 프레임을 모아 판정을 흔들리지 않게 한다. 최근 window 장 중 need 장 이상 통과면 통과."""

    def __init__(self, window: int = 10, need: int = 7):
        self.window, self.need = window, need
        self.history: list[bool] = []

    def add(self, ok: bool) -> None:
        self.history = (self.history + [ok])[-self.window:]

    @property
    def decided(self) -> bool:
        return len(self.history) >= self.window

    @property
    def passed(self) -> bool:
        return self.decided and sum(self.history) >= self.need


class RealSenseCamera:
    """D435 컬러 + 컬러에 맞춰 정렬한 깊이(미터)를 함께 읽는다. with 문으로 쓴다."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30, mirror: bool = True):
        self.size, self.fps, self.mirror = (width, height), fps, mirror
        self.pipeline = None

    def __enter__(self):
        import pyrealsense2 as rs
        self._rs = rs
        self.pipeline = rs.pipeline()
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, *self.size, rs.format.bgr8, self.fps)
        cfg.enable_stream(rs.stream.depth, *self.size, rs.format.z16, self.fps)
        profile = self.pipeline.start(cfg)
        self.depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
        self.align = rs.align(rs.stream.color)
        return self

    def read(self):
        frames = self.align.process(self.pipeline.wait_for_frames())
        color, depth = frames.get_color_frame(), frames.get_depth_frame()
        if not color or not depth:
            return None, None
        color_img = np.asanyarray(color.get_data()).copy()
        depth_m = np.asanyarray(depth.get_data()).astype(np.float32) * self.depth_scale
        if self.mirror:   # 앱과 같은 거울 화면. 컬러와 깊이를 같이 뒤집어야 좌표가 맞는다.
            color_img, depth_m = color_img[:, ::-1].copy(), depth_m[:, ::-1].copy()
        return color_img, depth_m

    def __exit__(self, *exc):
        if self.pipeline is not None:
            self.pipeline.stop()
        return False


def realsense_available() -> bool:
    try:
        import pyrealsense2 as rs
        return len(rs.context().query_devices()) > 0
    except Exception:
        return False
