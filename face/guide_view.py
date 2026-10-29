"""얼굴 확인 카메라 창 화면 (와이어프레임 10-B).

왼쪽 절반은 거울 카메라와 얼굴 자리(ROI) 타원만 보여 주고, 글자 안내는 넣지 않는다.
오른쪽 절반에 단계 목록을 한국어로 그리고 지금 단계만 크게 강조한다.
OpenCV 글꼴은 한글을 못 쓰므로 오른쪽 패널은 Pillow로 그린다.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

PANEL_W, HEIGHT = 640, 720
CANVAS_SIZE = (PANEL_W * 2, HEIGHT)          # 창 크기 (너비, 높이)
ROI_CENTER = (PANEL_W // 2, 370)
ROI_AXES = (150, 200)                         # 얼굴이 와야 할 타원의 가로·세로 반지름

GREEN, RED, YELLOW = (70, 200, 70), (40, 40, 230), (0, 200, 255)   # BGR
# 타원 색: 초록 = 지금 맞게 하는 중, 노랑 = 진짜 얼굴 확인 중·가림·품질 안내, 빨강 = 얼굴 없음·위치 틀림

# 10/29: 손님에게는 '입체 확인' 같은 기술 말 없이 할 일만 짧게
CHECK_LABELS = {
    "LIVE CHECK": "정면을 보고 잠시 멈추기",
    "DEPTH CHECK": "정면을 보고 잠시 멈추기",
}
PURPOSE_TITLES = {"ENROLL": "얼굴 등록", "LOGIN": "얼굴 로그인", "VERIFY": "얼굴 확인"}

FONT_FILES = {False: "malgun.ttf", True: "malgunbd.ttf"}
FONT_DIR = Path("C:/Windows/Fonts")
_fonts: dict = {}


def step_labels(challenges, purpose: str = "ENROLL") -> list[str]:
    return ["카메라 앞에 서기", *[CHECK_LABELS[c] for c in challenges], "확인 중"]


def current_step(calibrated: bool, step: int, total_challenges: int) -> int:
    """지금 강조할 단계 번호(0부터). 진짜 얼굴 확인이 끝나면 마지막 단계가 된다."""
    if not calibrated:
        return 0
    return 1 + min(step, total_challenges)


def fit_camera(frame):
    """카메라 프레임을 왼쪽 패널(640x720)에 맞게 키우고 가운데를 자른다."""
    h, w = frame.shape[:2]
    scale = HEIGHT / h
    resized = cv2.resize(frame, (round(w * scale), HEIGHT))
    offset = max(0, (resized.shape[1] - PANEL_W) // 2)
    view = resized[:, offset:offset + PANEL_W]
    if view.shape[1] < PANEL_W:
        pad = PANEL_W - view.shape[1]
        view = cv2.copyMakeBorder(view, 0, 0, pad // 2, pad - pad // 2, cv2.BORDER_CONSTANT)
    return view, scale, offset


def frame_in_roi(frame, face) -> bool:
    """원본 카메라 프레임 좌표의 얼굴이 왼쪽 패널의 ROI 타원 안에 있는지."""
    h, w = frame.shape[:2]
    scale = HEIGHT / h
    return face_in_roi(face, scale, max(0, (round(w * scale) - PANEL_W) // 2))


def face_in_roi(face, scale: float, offset: int) -> bool:
    """얼굴 중심이 타원 안쪽이고, 너무 작지 않으면 True."""
    x, y, w, h = map(float, face[:4])
    cx, cy = (x + w / 2) * scale - offset, (y + h / 2) * scale
    ax, ay = ROI_AXES
    dist = ((cx - ROI_CENTER[0]) / ax) ** 2 + ((cy - ROI_CENTER[1]) / ay) ** 2
    return dist < 0.5 and w * scale >= ax


def draw_camera(view, roi_color):
    """타원 바깥은 어둡게, 타원 테두리는 상태 색으로 그린다."""
    mask = np.zeros(view.shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, ROI_CENTER, ROI_AXES, 0, 0, 360, 255, -1)
    dark = (view * 0.4).astype(np.uint8)
    out = np.where(mask[:, :, None] == 255, view, dark)
    cv2.ellipse(out, ROI_CENTER, ROI_AXES, 0, 0, 360, roi_color, 6, cv2.LINE_AA)
    return out


def draw_face_id(progress: float, face_found: bool, done: bool = False):
    """로그인용 얼굴 모양 화면 (아이폰 Face ID처럼). 카메라 영상은 보여 주지 않는다.

    가운데 얼굴 기호(모서리 괄호·눈·코·입)와 둘레의 눈금 고리. 진행한 만큼 눈금이 초록으로 켜진다.
    얼굴을 못 찾으면 회색, 찾으면 진하게, 끝나면 전체 초록 + 체크.
    """
    out = np.full((HEIGHT, PANEL_W, 3), 250, dtype=np.uint8)
    cx, cy = ROI_CENTER
    base = (60, 60, 60) if face_found or done else (190, 190, 190)
    green = (90, 190, 70)
    color = green if done else base
    ticks, lit = 60, int(ticks_fraction(progress, done) * 60)
    for i in range(ticks):
        angle = 2 * np.pi * i / ticks - np.pi / 2
        r1, r2 = 205, 235
        p1 = (int(cx + r1 * np.cos(angle)), int(cy + r1 * np.sin(angle)))
        p2 = (int(cx + r2 * np.cos(angle)), int(cy + r2 * np.sin(angle)))
        cv2.line(out, p1, p2, green if i < lit else (215, 215, 215), 6, cv2.LINE_AA)
    s = 120   # 얼굴 기호 크기 (반)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):   # 네 모서리 괄호
        corner = (cx + sx * s, cy + sy * s)
        cv2.line(out, corner, (corner[0] - sx * 50, corner[1]), color, 8, cv2.LINE_AA)
        cv2.line(out, corner, (corner[0], corner[1] - sy * 50), color, 8, cv2.LINE_AA)
    if done:
        cv2.polylines(out, [np.array([(cx - 50, cy), (cx - 12, cy + 40), (cx + 60, cy - 45)])], False,
                      green, 14, cv2.LINE_AA)
    else:
        for ex in (-40, 40):
            cv2.line(out, (cx + ex, cy - 40), (cx + ex, cy - 15), color, 8, cv2.LINE_AA)
        cv2.polylines(out, [np.array([(cx, cy - 20), (cx, cy + 15), (cx - 12, cy + 15)])], False, color, 6,
                      cv2.LINE_AA)
        cv2.ellipse(out, (cx, cy + 30), (40, 22), 0, 20, 160, color, 7, cv2.LINE_AA)
    return out


def ticks_fraction(progress: float, done: bool) -> float:
    return 1.0 if done else max(0.0, min(1.0, progress))


def _font(size: int, bold: bool = False):
    from PIL import ImageFont
    key = (size, bold)
    if key not in _fonts:
        try:
            _fonts[key] = ImageFont.truetype(str(FONT_DIR / FONT_FILES[bold]), size)
        except OSError:
            _fonts[key] = ImageFont.load_default(size)
    return _fonts[key]


def render_panel(title: str, labels, current: int, alert: str, progress: float):
    """오른쪽 안내 패널. 끝난 단계 ✓ 회색, 지금 단계 ▶ 크게·진하게, 남은 단계 ○ 흐리게."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (PANEL_W, HEIGHT), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 32), title, font=_font(40, True), fill=(20, 20, 20))
    d.text((40, 90), "왼쪽 화면을 보면서 차례대로 따라 해 주세요", font=_font(22), fill=(110, 110, 110))
    y = 150
    for i, label in enumerate(labels):
        if i == current:
            d.rounded_rectangle((28, y - 8, PANEL_W - 28, y + 60), 12, fill=(25, 25, 25))
            d.text((48, y + 6), f"▶  {i + 1}  {label}", font=_font(32, True), fill=(255, 255, 255))
            y += 84
        else:
            done = i < current
            color = (150, 150, 150) if done else (195, 195, 195)
            if done:   # 맑은 고딕에 ✓ 글자가 없어 선으로 그린다
                d.line([(50, y + 18), (58, y + 27), (72, y + 8)], fill=(70, 170, 70), width=4)
            else:
                d.ellipse((50, y + 7, 70, y + 27), outline=color, width=2)
            d.text((86, y), f"{i + 1}  {label}", font=_font(26), fill=color)
            y += 58
    if alert:
        d.text((40, HEIGHT - 160), alert, font=_font(26, True), fill=(220, 40, 40))
    bar_w = int((PANEL_W - 80) * max(0.0, min(1.0, progress)))
    d.rounded_rectangle((40, HEIGHT - 100, PANEL_W - 40, HEIGHT - 80), 8, fill=(225, 225, 225))
    if bar_w > 0:
        d.rounded_rectangle((40, HEIGHT - 100, 40 + bar_w, HEIGHT - 80), 8, fill=(70, 200, 70))
    d.text((40, HEIGHT - 62), "ESC 취소 · 사진은 저장하지 않고 특징값만 암호화해 저장",
           font=_font(20), fill=(120, 120, 120))
    return np.asarray(img)[:, :, ::-1].copy()


def compose(frame, face, count: int, challenges, calibrated: bool, step: int,
            purpose: str, progress: float, motion_ok: bool = False, done: bool = False, alert: str = ""):
    """카메라 프레임과 현재 진행 상태로 1280x720 창 이미지를 만든다.

    alert는 가림·품질 검사(face/quality.py) 안내 문구다. 있으면 타원을 노랑으로 하고 그 문구를 보여 준다.

    등록(ENROLL)은 거울 카메라를 보여 주고, 로그인·확인은 얼굴을 직접 보여 주지 않고
    얼굴 모양 기호만 보여 준다 (아이폰처럼).
    """
    view, scale, offset = fit_camera(frame)
    in_roi = face is not None and face_in_roi(face, scale, offset)
    labels = step_labels(challenges, purpose)
    current = current_step(calibrated, step, len(challenges))
    moving = calibrated and step < len(challenges)
    if face is None:
        roi_color = RED
        if alert:
            pass
        else:   # 카메라 화면을 보여 주지 않으므로 '타원' 대신 카메라 앞에 서라고만 한다
            alert = "한 사람만 카메라 앞에 서 주세요" if count > 1 else "카메라 앞에 서 주세요"
    elif alert:
        roi_color = YELLOW
    elif moving:
        # 진짜 얼굴 확인 중: 판정이 '진짜'로 나오는 동안 초록, 아니면 노랑.
        roi_color = GREEN if motion_ok else YELLOW
    elif in_roi:
        roi_color = GREEN
    else:
        roi_color = RED
        alert = "얼굴을 타원 안에 맞춰 주세요 (너무 멀면 조금 가까이)"
    # 10/29: 등록도 로그인처럼 카메라 영상 대신 얼굴 기호만 (타원에 맞추기 어렵다는 의견). 50cm 안이면 된다.
    left = draw_face_id(progress, face is not None, done)
    if face is not None and roi_color == RED:
        alert = ""              # 타원에 맞출 필요가 없다
    right = render_panel(PURPOSE_TITLES.get(purpose, purpose), labels, current, alert, progress)
    return np.hstack([left, right])
