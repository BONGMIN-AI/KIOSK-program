"""키오스크 설정 · 광고 배너 (11/02 B7·B8). 운영자 화면에서 바꾸고 settings에 저장한다.

settings["kiosk"]  = {idle_seconds, warn_seconds, more_order_seconds, slide_seconds, away_seconds}
settings["ticket_sales"] = True/False   (승차권 탭 — 예전부터 쓰던 키 그대로)
settings["presence"] = True/False       (카메라 사람 감지: 다가오면 시작 · 자리 비움 확인, 11/02 C)
settings["slides"] = [{"file", "caption", "fit", "on"}, ...]   (시작 화면 왼쪽 광고, 위에서부터 순서)
"""

DEFAULT_SLIDES = [
    {"file": "promo_photo.webp", "caption": "", "fit": "contain", "on": True},
    {"file": "menu/M006_카라멜마키아토.png", "caption": "시그니처 · 카라멜마키아토", "fit": "cover", "on": True},
    {"file": "promo_smile.webp", "caption": "", "fit": "contain", "on": True},
    {"file": "menu/M012_딸기라떼.png", "caption": "계절 메뉴 · 딸기라떼", "fit": "cover", "on": True},
    {"file": "menu/M031_레몬에이드.png", "caption": "상큼하게 · 레몬에이드", "fit": "cover", "on": True},
    {"file": "menu/M044_치즈케이크.png", "caption": "커피와 함께 · 치즈케이크", "fit": "cover", "on": True},
]

# (키, 화면 이름, 단위, 기본값, 가장 작은 값, 가장 큰 값)
KIOSK_FIELDS = [
    ("idle_seconds", "손님 화면 무입력 복귀", "초", 60, 20, 300),
    ("warn_seconds", "복귀 전 경고", "초", 15, 5, 60),
    ("more_order_seconds", "'더 주문하시겠어요?' 시간", "초", 15, 5, 60),
    ("slide_seconds", "시작 화면 광고 넘김", "초", 5, 2, 30),
    ("away_seconds", "자리 비움 확인까지", "초", 10, 5, 120),
]
KIOSK_DEFAULTS = {key: default for key, _name, _unit, default, _low, _high in KIOSK_FIELDS}


def load_kiosk(settings: dict | None) -> dict:
    return {**KIOSK_DEFAULTS, **((settings or {}).get("kiosk") or {})}


def validate_kiosk(raw: dict) -> dict:
    result = {}
    for key, name, unit, _default, low, high in KIOSK_FIELDS:
        try:
            value = int(str(raw.get(key, KIOSK_DEFAULTS[key])).replace(unit, "").strip())
        except ValueError as exc:
            raise ValueError(f"{name}은(는) 숫자로 입력하세요") from exc
        if not low <= value <= high:
            raise ValueError(f"{name}은(는) {low}~{high}{unit} 사이로 입력하세요")
        result[key] = value
    if result["warn_seconds"] >= result["idle_seconds"]:
        raise ValueError("복귀 전 경고는 무입력 복귀 시간보다 짧아야 해요")
    return result


def presence_on(settings: dict | None) -> bool:
    return (settings or {}).get("presence", True) is not False


def save_kiosk(vault, raw: dict, ticket_sales: bool, presence: bool = True) -> dict:
    settings = vault.read("settings", default={})
    settings["kiosk"] = validate_kiosk(raw)
    settings["ticket_sales"] = bool(ticket_sales)
    settings["presence"] = bool(presence)
    vault.write("settings", settings)
    return settings["kiosk"]


def all_slides(settings: dict | None) -> list[dict]:
    """운영자 화면용: 숨긴 것까지 순서대로."""
    stored = (settings or {}).get("slides")
    return [dict(slide) for slide in (stored if stored else DEFAULT_SLIDES)]


def shown_slides(settings: dict | None) -> list[tuple]:
    """시작 화면용: 보이기로 둔 광고만 (그림, 글, 맞춤). 하나도 없으면 기본 광고."""
    slides = [(s["file"], s.get("caption", ""), s.get("fit", "cover")) for s in all_slides(settings) if s.get("on")]
    return slides or [(s["file"], s["caption"], s["fit"]) for s in DEFAULT_SLIDES]


def save_slides(vault, slides: list[dict]) -> None:
    if not any(slide.get("on") for slide in slides):
        raise ValueError("광고를 한 장 이상은 보이게 두세요")
    settings = vault.read("settings", default={})
    settings["slides"] = [{"file": s["file"], "caption": s.get("caption", ""), "fit": s.get("fit", "cover"),
                           "on": bool(s.get("on"))} for s in slides]
    vault.write("settings", settings)
