"""공개 모델로 만든 얼굴 비교 · 사진 판정 (10/29 SFace·고개 동작에서 교체).

- ArcFace (InsightFace buffalo_l 의 w600k_r50): 정렬한 얼굴 112x112 → 512개 숫자.
  InsightFace 코드는 MIT, 모델 가중치는 비상업 연구용이다 (수업 과제 사용, 출처 표기).
- MiniFASNet V2 + V1SE (minivision Silent-Face-Anti-Spoofing, Apache-2.0):
  사진 한 장으로 진짜 얼굴인지, 종이 사진·휴대폰 화면인지 판정한다. 고개 동작이 필요 없다.

둘 다 onnxruntime CPU로 키오스크 안에서만 돈다. 사진·영상은 저장하지 않는다.
"""
from __future__ import annotations

import cv2
import numpy as np

from . import FaceError

# ArcFace 학습 때 쓴 112x112 얼굴의 5점 위치 (화면 왼쪽 눈, 오른쪽 눈, 코, 왼쪽 입꼬리, 오른쪽 입꼬리)
ARCFACE_TEMPLATE = np.array([
    [38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
    [41.5493, 92.3655], [70.7299, 92.2041],
], dtype=np.float32)
REAL_CLASS = 1                 # MiniFASNet 출력: 0 = 종이 사진, 1 = 진짜, 2 = 화면
REAL_THRESHOLD = 0.6           # 두 모델 평균 '진짜' 확률이 이 값 이상이면 진짜로 본다


def _session(path):
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.log_severity_level = 3
    options.intra_op_num_threads = 4     # 코어를 다 쓰면 카메라·화면 처리와 부딪혀 오히려 느려진다
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def landmarks(face) -> np.ndarray:
    """YuNet 결과에서 5점을 ArcFace 순서(화면 기준 왼쪽 → 오른쪽)로 꺼낸다."""
    points = np.asarray(face[4:14], dtype=np.float32).reshape(5, 2)
    eyes = points[:2][np.argsort(points[:2, 0])]
    mouth = points[3:5][np.argsort(points[3:5, 0])]
    return np.vstack([eyes, points[2:3], mouth])


class ArcFace:
    def __init__(self, model_path):
        self.session = _session(model_path)
        self.input_name = self.session.get_inputs()[0].name

    @staticmethod
    def align(frame, face) -> np.ndarray:
        matrix, _inliers = cv2.estimateAffinePartial2D(landmarks(face), ARCFACE_TEMPLATE, method=cv2.LMEDS)
        if matrix is None:
            raise FaceError("얼굴 위치를 맞추지 못했어요. 정면을 봐 주세요")
        return cv2.warpAffine(frame, matrix, (112, 112), borderValue=0)

    def feature(self, frame, face) -> np.ndarray:
        """길이 1로 맞춘 512개 숫자. 두 얼굴의 내적이 곧 코사인 유사도다."""
        crop = self.align(frame, face)
        blob = cv2.dnn.blobFromImage(crop, 1 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True)
        vector = self.session.run(None, {self.input_name: blob})[0].reshape(-1).astype(np.float32)
        norm = float(np.linalg.norm(vector))
        if norm == 0:
            raise FaceError("얼굴 특징을 만들지 못했습니다")
        return vector / norm


def crop_for_antispoof(frame, face, scale: float, size: int = 80) -> np.ndarray:
    """얼굴 박스를 scale 배로 넓혀 자른다 (원본 저장소와 같은 방식)."""
    height, width = frame.shape[:2]
    x, y, w, h = (float(v) for v in face[:4])
    w, h = max(w, 1.0), max(h, 1.0)
    scale = min((height - 1) / h, (width - 1) / w, scale)
    cx, cy = x + w / 2, y + h / 2
    x1, y1 = max(0, int(cx - w * scale / 2)), max(0, int(cy - h * scale / 2))
    x2, y2 = min(width - 1, int(cx + w * scale / 2)), min(height - 1, int(cy + h * scale / 2))
    crop = frame[y1:y2 + 1, x1:x2 + 1]
    if crop.size == 0:
        crop = frame
    return cv2.resize(crop, (size, size))


class AntiSpoof:
    """MiniFASNet 두 개(넓게 자른 것 · 더 넓게 자른 것)의 '진짜' 확률 평균."""

    def __init__(self, models):
        self.models = [(_session(path), scale) for path, scale in models]

    def real_score(self, frame, face) -> float:
        total = 0.0
        for session, scale in self.models:
            crop = crop_for_antispoof(frame, face, scale).astype(np.float32)      # BGR 그대로, 정규화 없음
            blob = np.transpose(crop, (2, 0, 1))[None]
            logits = session.run(None, {session.get_inputs()[0].name: blob})[0][0]
            probs = np.exp(logits - logits.max())
            total += float(probs[REAL_CLASS] / probs.sum())
        return total / len(self.models)

    def is_real(self, frame, face) -> bool:
        return self.real_score(frame, face) >= REAL_THRESHOLD
