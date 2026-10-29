"""대기 화면 로고 움직임(D-2 기어 회전 · D-3 김)에 쓸 로고 조각을 만든다.

사용: python tools/make_logo_parts.py
입력 gui/assets/logo_main.png → 출력
  logo_idle_base.png  : 김과 기어를 지운 로고 (지운 자리는 주변 색으로 메움)
  logo_idle_front.png : 기어 앞을 가리는 숟가락 앞쪽 테두리만 (돌아가는 기어 위에 다시 그린다)
기어·김은 gui/screens/idle.py가 그 자리에 직접 그린다. 원본 logo_main.png는 바꾸지 않는다.
"""
from pathlib import Path

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent.parent / "gui" / "assets"
GEAR_CENTER = (1523, 519)       # 원본 로고(1774×887) 기준. idle.py의 GEAR_CENTER와 같아야 한다
GEAR_RADIUS = 68
STEAM_AREA = (250, 452, 1452, 1580)   # (위, 아래, 왼쪽, 오른쪽) — 김만 있는 투명 바탕 자리
LIP_TOP = GEAR_CENTER[1] + 30          # 이보다 아래의 숟가락은 기어 앞에 있다


def read(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)


def write(path, image):
    cv2.imencode(".png", image)[1].tofile(str(path))


def main():
    logo = read(ASSETS / "logo_main.png")
    height, width = logo.shape[:2]
    b, g, r, alpha = [logo[..., i].astype(int) for i in range(4)]
    ys, xs = np.mgrid[0:height, 0:width]
    cx, cy = GEAR_CENTER
    in_circle = (xs - cx) ** 2 + (ys - cy) ** 2 <= (GEAR_RADIUS + 6) ** 2
    orange = (r - b > 70) & (r > 140) & (alpha > 40)       # 기어(카라멜색)와 밝은 테두리
    gear = in_circle & (orange | ((r > 200) & (alpha > 40))) & (ys < LIP_TOP + 8)
    gear = cv2.dilate(gear.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    gear &= in_circle

    front = logo.copy()
    lip = in_circle & (ys >= LIP_TOP) & ~orange
    front[~lip] = 0
    write(ASSETS / "logo_idle_front.png", front)

    base = logo.copy()
    mask = gear.astype(np.uint8) * 255
    base[..., :3] = cv2.inpaint(np.ascontiguousarray(logo[..., :3]), mask, 7, cv2.INPAINT_TELEA)
    base[..., 3] = cv2.inpaint(np.ascontiguousarray(logo[..., 3]), mask, 7, cv2.INPAINT_TELEA)
    top, bottom, left, right = STEAM_AREA
    base[top:bottom, left:right, 3] = 0
    write(ASSETS / "logo_idle_base.png", base)
    print("저장: logo_idle_base.png, logo_idle_front.png")


if __name__ == "__main__":
    main()
