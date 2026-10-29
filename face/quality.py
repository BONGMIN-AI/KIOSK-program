"""얼굴 사진 한 장의 품질·가림 검사 (얼굴 인증 세부 흐름 F3 가림 · F4 품질).

통과하면 빈 문자열, 아니면 손님에게 보여 줄 안내 문구를 돌려준다.
검사를 통과한 프레임만 사진 판정·얼굴 비교에 쓴다.

가림 판정은 YuNet 5점 위치 주변의 밝기·피부색을 보는 근사 판정이다.
살색 마스크나 아주 어두운 조명에서는 틀릴 수 있다 (수업용 수준).
"""
from __future__ import annotations

import cv2
import numpy as np

from .engines import landmarks

MIN_FACE_WIDTH = 90            # 640x480 화면에서 이보다 작으면 너무 멀다
MAX_YAW = 0.15                 # 코가 눈 사이 거리의 15%(약 18도) 넘게 옆으로 가면 정면이 아니다
MIN_BRIGHTNESS = 55            # 얼굴 평균 밝기 (0~255)
MIN_SHARPNESS = 20             # 라플라시안 분산. 이보다 작으면 흔들림·초점 나감
EYE_SKIN_RATIO = 0.25          # 두 눈 주변 모두 피부색이 이보다 적고 어두우면 선글라스
EYE_DARK_RATIO = 0.6           # (그늘진 눈은 어두워도 피부색이 남아 있어 통과한다)
MASK_SKIN_RATIO = 0.15         # 입 주변 피부색(입술 포함) 비율이 이보다 낮으면 마스크
REFERENCE_SKIN_RATIO = 0.5     # 비교 기준(미간) 자체가 피부로 보일 때만 마스크 판정

TOO_FAR = "카메라에 조금 더 가까이 와 주세요"
NOT_FRONT = "고개를 돌리지 말고 정면을 봐 주세요"
TOO_DARK = "얼굴이 너무 어두워요. 밝은 곳에서 해 주세요"
BLURRY = "움직이지 말고 잠시 멈춰 주세요"
EYES_COVERED = "눈이 가려졌어요. 선글라스나 모자를 벗어 주세요"
MASK = "입이 가려졌어요. 마스크를 벗어 주세요"
COVERED = (EYES_COVERED, MASK)


def _patch(image, center, half_w, half_h):
    height, width = image.shape[:2]
    cx, cy = center
    x1, x2 = int(max(0, cx - half_w)), int(min(width, cx + half_w))
    y1, y2 = int(max(0, cy - half_h)), int(min(height, cy + half_h))
    return image[y1:y2, x1:x2]


def skin_ratio(patch_bgr) -> float:
    if patch_bgr.size == 0:
        return 0.0
    ycrcb = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2YCrCb)
    _y, cr, cb = cv2.split(ycrcb)
    skin = (cr >= 133) & (cr <= 190) & (cb >= 77) & (cb <= 135)     # 190까지: 입술도 포함
    return float(skin.mean())


def yaw(face) -> float:
    left_eye, right_eye, nose = landmarks(face)[:3]
    eye_dist = max(float(right_eye[0] - left_eye[0]), 1.0)
    return (float(nose[0]) - (left_eye[0] + right_eye[0]) / 2) / eye_dist


def check(frame, face) -> str:
    x, y, w, h = (float(v) for v in face[:4])
    if w < MIN_FACE_WIDTH:
        return TOO_FAR
    if abs(yaw(face)) > MAX_YAW:
        return NOT_FRONT

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    box = gray[int(max(0, y)):int(y + h), int(max(0, x)):int(x + w)]
    if box.size == 0:
        return TOO_FAR
    if float(box.mean()) < MIN_BRIGHTNESS:
        return TOO_DARK
    if cv2.Laplacian(cv2.resize(box, (128, 128)), cv2.CV_64F).var() < MIN_SHARPNESS:
        return BLURRY

    left_eye, right_eye, nose, mouth_left, mouth_right = landmarks(face)
    eye_dist = max(float(right_eye[0] - left_eye[0]), 1.0)
    nose_light = float(_patch(gray, nose, eye_dist * 0.18, eye_dist * 0.18).mean() or 1.0)
    eye_patches = [(_patch(frame, eye, eye_dist * 0.3, eye_dist * 0.18),
                    _patch(gray, eye, eye_dist * 0.3, eye_dist * 0.18)) for eye in (left_eye, right_eye)]
    if all(skin_ratio(color) < EYE_SKIN_RATIO and float(g.mean() or 0.0) < nose_light * EYE_DARK_RATIO
           for color, g in eye_patches):
        return EYES_COVERED

    between_eyes = (left_eye + right_eye) / 2 - np.array([0.0, eye_dist * 0.1])
    reference = skin_ratio(_patch(frame, between_eyes, eye_dist * 0.2, eye_dist * 0.12))
    mouth = (mouth_left + mouth_right) / 2
    mouth_skin = skin_ratio(_patch(frame, mouth, eye_dist * 0.45, eye_dist * 0.25))
    if reference >= REFERENCE_SKIN_RATIO and mouth_skin < MASK_SKIN_RATIO:
        return MASK
    return ""
