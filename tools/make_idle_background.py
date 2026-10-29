"""대기 화면 그림에서 박혀 있는 로고와 안내 글자를 지운 배경을 만든다.

사용: python tools/make_idle_background.py
입력 gui/assets/idle_bg.webp → 출력 gui/assets/idle_bg_clean.png
지운 자리는 프로그램(gui/screens/idle.py)이 로고와 글자를 다시 그린다.
손가락 아이콘·화살표 원·양옆 선은 그대로 둔다.
"""
from pathlib import Path

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent.parent / "gui" / "assets"

# 원본 그림(1672×941) 안에서 지울 영역: (위, 아래, 왼쪽, 오른쪽)
LOGO_AREA = (15, 262, 450, 1265)
STEAM_AREA = (20, 150, 1140, 1255)      # 로고 위 김은 통째로 지운다
START_TEXT_AREA = (778, 846, 575, 1168)
APPROACH_TEXT_AREA = (846, 886, 600, 1112)


def area_mask(shape, area, condition):
    top, bottom, left, right = area
    inside = np.zeros(shape, bool)
    inside[top:bottom, left:right] = True
    return inside & condition


def make_mask(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    light = gray.astype(int)
    background = cv2.medianBlur(gray, 81).astype(int)   # 주변 바탕 밝기
    saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[..., 1]

    different = (light < background - 14) | (light > background + 10) | (saturation > 90)
    mask = area_mask(gray.shape, LOGO_AREA, different)
    top, bottom, left, right = STEAM_AREA
    mask[top:bottom, left:right] = True
    mask |= area_mask(gray.shape, START_TEXT_AREA,
                      (light < background - 20) | (light > background + 10))
    mask |= area_mask(gray.shape, APPROACH_TEXT_AREA,
                      (light < background - 10) | (light > background + 10))

    mask = mask.astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return cv2.dilate(mask, kernel)


def main():
    # 한글 경로라 cv2.imread 대신 바이트로 읽고 쓴다.
    image = cv2.imdecode(np.fromfile(ASSETS / "idle_bg.webp", np.uint8), cv2.IMREAD_COLOR)
    mask = make_mask(image)
    clean = cv2.inpaint(image, mask, 15, cv2.INPAINT_TELEA)
    soft = cv2.GaussianBlur(clean, (0, 0), 2.0)
    clean = np.where(mask[..., None] > 0, soft, clean)   # 메운 자리만 살짝 흐리게
    output = ASSETS / "idle_bg_clean.png"
    cv2.imencode(".png", clean)[1].tofile(output)
    print("저장:", output)


if __name__ == "__main__":
    main()
