"""포인트·쿠폰 정책과 기간 이벤트. 운영자 화면에서 바꾸고 settings 데이터셋에 저장한다.

settings["point_policy"] = {
    "base_rate": 1.0,            # 기본 적립률(%) — 실제 결제한 현금 기준
    "point_unit": 100,           # 포인트 사용 단위
    "min_use": 100,              # 한 번에 쓸 수 있는 최소 포인트
    "max_use_percent": 100,      # 결제액 중 포인트로 낼 수 있는 최대 비율(%)
    "visit_coupon_every": 5,     # N번째 방문마다 쿠폰 (0이면 발행 안 함)
    "visit_coupon_amount": 1000, # 방문 쿠폰 금액
    "visit_coupon_days": 0,      # 쿠폰 유효 일수 (0이면 그해 12월 31일까지)
    "events": [ {이벤트}, ... ],
}

이벤트 = {
    "id": "EV001", "name": "가을 더블 포인트", "enabled": True,
    "start": "2026-10-20", "end": "2026-10-31",   # 날짜 포함 범위
    "weekdays": [0, 1, 2, 3, 4],                  # 0=월 … 6=일, 빈 목록이면 매일
    "hours": [14, 17],                            # 14시 이상 17시 미만, 없으면 하루 종일
    "categories": ["커피"],                       # 빈 목록이면 전체 메뉴
    "rate": 3.0,                                  # 해당 메뉴의 적립률(%) — 기본보다 클 때만 의미
    "bonus_points": 200,                          # 조건을 만족한 주문마다 추가 포인트
    "min_order": 10000,                           # 보너스 포인트를 받을 최소 결제액
    "member_only": True,                          # 지금은 회원만 적립하므로 항상 True
    "theme": "season",                            # 손님 화면 색: basic(기본)·season(시즌)·festival(축제)
    "message": "회원은 커피 3% 적립 + …",          # 배너·대기 화면 띠에 보일 문구 (비우면 자동)
}
"""
from datetime import date, datetime, timedelta

WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
THEMES = {"basic": "기본", "season": "시즌", "festival": "축제"}
MESSAGE_LIMIT = 60

DEFAULT_POLICY = {
    "base_rate": 1.0,
    "point_unit": 100,
    "min_use": 100,
    "max_use_percent": 100,
    "visit_coupon_every": 5,
    "visit_coupon_amount": 1000,
    "visit_coupon_days": 0,
    "events": [],
}


def load_policy(settings: dict | None) -> dict:
    """저장된 값이 없거나 일부만 있어도 기본값으로 채워 돌려준다."""
    stored = dict((settings or {}).get("point_policy") or {})
    policy = {**DEFAULT_POLICY, **stored}
    policy["events"] = [dict(e) for e in stored.get("events", [])]
    return policy


def validate_policy(raw: dict) -> dict:
    policy = {**DEFAULT_POLICY, **raw}
    rate = float(policy["base_rate"])
    if not 0 <= rate <= 20:
        raise ValueError("기본 적립률은 0~20% 사이로 입력하세요")
    unit = int(policy["point_unit"])
    if unit not in (1, 10, 100, 1000):
        raise ValueError("포인트 사용 단위는 1·10·100·1000 중 하나로 입력하세요")
    min_use = int(policy["min_use"])
    if min_use < 0 or min_use % unit:
        raise ValueError("최소 사용 포인트는 0 이상, 사용 단위의 배수여야 합니다")
    max_percent = int(policy["max_use_percent"])
    if not 0 <= max_percent <= 100:
        raise ValueError("포인트 최대 사용 비율은 0~100% 사이로 입력하세요")
    every = int(policy["visit_coupon_every"])
    amount = int(policy["visit_coupon_amount"])
    days = int(policy["visit_coupon_days"])
    if every < 0 or amount < 0 or days < 0:
        raise ValueError("방문 쿠폰 값은 0 이상으로 입력하세요")
    if every and amount == 0:
        raise ValueError("방문 쿠폰을 발행하려면 쿠폰 금액을 1원 이상으로 입력하세요")
    return {
        "base_rate": rate, "point_unit": unit, "min_use": min_use, "max_use_percent": max_percent,
        "visit_coupon_every": every, "visit_coupon_amount": amount, "visit_coupon_days": days,
        "events": [validate_event(e) for e in policy.get("events", [])],
    }


def _parse_date(text: str, label: str) -> str:
    try:
        return date.fromisoformat(str(text).strip()).isoformat()
    except ValueError as exc:
        raise ValueError(f"{label}은(는) 2026-10-31 형식으로 입력하세요") from exc


def parse_weekdays(text) -> list[int]:
    """'월,수,금' 또는 '평일'/'주말'/'' → [0, 2, 4]"""
    if isinstance(text, list):
        values = text
    else:
        text = (text or "").replace(" ", "")
        if text in ("", "매일"):
            return []
        if text == "평일":
            return [0, 1, 2, 3, 4]
        if text == "주말":
            return [5, 6]
        values = []
        for part in text.split(","):
            if part not in WEEKDAY_NAMES:
                raise ValueError("요일은 월,화,수,목,금,토,일 / 평일 / 주말 / 매일 로 입력하세요")
            values.append(WEEKDAY_NAMES.index(part))
    days = sorted(set(int(v) for v in values))
    if any(d < 0 or d > 6 for d in days):
        raise ValueError("요일 값이 올바르지 않습니다")
    return days


def parse_hours(text):
    """'14-17' → [14, 17], '' → None"""
    if isinstance(text, list) or text is None:
        hours = text
    else:
        text = text.replace(" ", "")
        if not text:
            return None
        try:
            hours = [int(x) for x in text.split("-")]
        except ValueError as exc:
            raise ValueError("시간대는 14-17 처럼 입력하세요 (14시 이상 17시 미만)") from exc
    if hours is None:
        return None
    if len(hours) != 2 or not 0 <= hours[0] < hours[1] <= 24:
        raise ValueError("시간대는 0~24 사이에서 시작 < 끝 으로 입력하세요")
    return hours


def validate_event(raw: dict) -> dict:
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("이벤트 이름을 입력하세요")
    start = _parse_date(raw.get("start", ""), "시작일")
    end = _parse_date(raw.get("end", ""), "종료일")
    if end < start:
        raise ValueError("종료일이 시작일보다 빠릅니다")
    rate = float(raw.get("rate") or 0)
    bonus = int(raw.get("bonus_points") or 0)
    min_order = int(raw.get("min_order") or 0)
    if not 0 <= rate <= 50:
        raise ValueError("이벤트 적립률은 0~50% 사이로 입력하세요")
    if bonus < 0 or min_order < 0:
        raise ValueError("보너스 포인트와 최소 결제액은 0 이상이어야 합니다")
    if rate == 0 and bonus == 0:
        raise ValueError("이벤트 적립률이나 보너스 포인트 중 하나는 입력하세요")
    theme = raw.get("theme") or "basic"
    if theme not in THEMES:
        raise ValueError("테마는 기본·시즌·축제 중에서 고르세요")
    message = str(raw.get("message") or "").strip()
    if len(message) > MESSAGE_LIMIT:
        raise ValueError(f"배너 문구는 {MESSAGE_LIMIT}자 이내로 입력하세요")
    categories = raw.get("categories") or []
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    return {
        "id": str(raw.get("id") or ""),
        "name": name,
        "enabled": bool(raw.get("enabled", True)),
        "start": start,
        "end": end,
        "weekdays": parse_weekdays(raw.get("weekdays", [])),
        "hours": parse_hours(raw.get("hours")),
        "categories": sorted(set(categories)),
        "rate": rate,
        "bonus_points": bonus,
        "min_order": min_order,
        "member_only": True,
        "theme": theme,
        "message": message,
    }


def upsert_event(policy: dict, raw: dict) -> tuple[dict, dict]:
    """id가 있으면 수정, 없으면 EV001 같은 새 id로 추가한다."""
    event = validate_event(raw)
    events = [dict(e) for e in policy.get("events", [])]
    if event["id"] and any(e["id"] == event["id"] for e in events):
        events = [event if e["id"] == event["id"] else e for e in events]
    else:
        numbers = [int(e["id"][2:]) for e in events if e.get("id", "").startswith("EV") and e["id"][2:].isdigit()]
        event["id"] = f"EV{(max(numbers) + 1 if numbers else 1):03d}"
        events.append(event)
    return {**policy, "events": events}, event


def remove_event(policy: dict, event_id: str) -> dict:
    events = [e for e in policy.get("events", []) if e["id"] != event_id]
    if len(events) == len(policy.get("events", [])):
        raise ValueError("삭제할 이벤트가 없습니다")
    return {**policy, "events": events}


def event_is_active(event: dict, now: datetime) -> bool:
    if not event.get("enabled", True):
        return False
    today = now.date().isoformat()
    if not event["start"] <= today <= event["end"]:
        return False
    if event.get("weekdays") and now.weekday() not in event["weekdays"]:
        return False
    hours = event.get("hours")
    if hours and not hours[0] <= now.hour < hours[1]:
        return False
    return True


def active_events(policy: dict, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    return [e for e in policy.get("events", []) if event_is_active(e, now)]


def event_status(event: dict, now: datetime | None = None) -> str:
    now = now or datetime.now()
    today = now.date().isoformat()
    if not event.get("enabled", True):
        return "꺼짐"
    if today < event["start"]:
        return "예정"
    if today > event["end"]:
        return "종료"
    return "진행 중" if event_is_active(event, now) else "기간 중(시간·요일 외)"


def describe_event(event: dict) -> str:
    days = "매일" if not event.get("weekdays") else ",".join(WEEKDAY_NAMES[d] for d in event["weekdays"])
    hours = "종일" if not event.get("hours") else f"{event['hours'][0]}~{event['hours'][1]}시"
    scope = "전체 메뉴" if not event.get("categories") else "·".join(event["categories"])
    parts = []
    if event.get("rate"):
        parts.append(f"적립 {event['rate']:g}%")
    if event.get("bonus_points"):
        cond = f" ({event['min_order']:,}원 이상)" if event.get("min_order") else ""
        parts.append(f"보너스 +{event['bonus_points']:,}P{cond}")
    return f"{event['start']}~{event['end']} · {days} · {hours} · {scope} · " + " · ".join(parts)


def banner_message(event: dict) -> str:
    """손님 화면에 보일 짧은 문구. 운영자가 적은 문구가 없으면 혜택으로 만든다."""
    if event.get("message"):
        return event["message"]
    scope = "전 메뉴" if not event.get("categories") else "·".join(event["categories"])
    parts = []
    if event.get("rate"):
        parts.append(f"{scope} {event['rate']:g}% 적립")
    if event.get("bonus_points"):
        cond = f"{event['min_order'] // 10000:g}만원 이상 " if event.get("min_order") else ""
        parts.append(f"{cond}{event['bonus_points']:,}P")
    return "회원은 " + " + ".join(parts) + f" · {int(event['end'][5:7])}/{int(event['end'][8:10])}까지"


def display_event(policy: dict, now: datetime | None = None) -> dict | None:
    """지금 진행 중인 이벤트 하나를 손님 화면용으로 돌려준다(없으면 None). 여러 개면 목록의 앞쪽."""
    events = active_events(policy, now)
    if not events:
        return None
    event = events[0]
    return {"id": event["id"], "name": event["name"], "theme": event.get("theme", "basic"),
            "message": banner_message(event)}


def calculate_points(policy: dict, lines: list[dict], menu: dict, final_total: int,
                     now: datetime | None = None) -> dict:
    """실제 결제액을 메뉴별로 나눠 메뉴마다 가장 높은 적립률을 적용한다.

    쿠폰·포인트 할인은 각 줄 금액 비율대로 나눠 뺀다. 보너스 포인트는 조건을 만족한
    이벤트마다 한 번씩 더한다.
    """
    events = active_events(policy, now)
    total = sum(line["subtotal"] for line in lines)
    if total <= 0 or final_total <= 0:
        return {"earned": 0, "base_rate": policy["base_rate"], "events": [], "bonus": 0}
    raw_points = 0.0
    used_events = set()
    for line in lines:
        category = menu.get(line["menu_id"], {}).get("category")
        rate, source = policy["base_rate"], None
        for event in events:
            if (not event["categories"] or category in event["categories"]) and event["rate"] > rate:
                rate, source = event["rate"], event["name"]
        if source:
            used_events.add(source)
        raw_points += line["subtotal"] * final_total / total * rate / 100
    bonus = 0
    categories = {menu.get(line["menu_id"], {}).get("category") for line in lines}
    for event in events:
        in_scope = not event["categories"] or categories & set(event["categories"])
        if event["bonus_points"] and in_scope and final_total >= event["min_order"]:
            bonus += event["bonus_points"]
            used_events.add(event["name"])
    return {"earned": int(raw_points) + bonus, "base_rate": policy["base_rate"],
            "events": sorted(used_events), "bonus": bonus}


def coupon_expiry(policy: dict, today: date | None = None) -> str:
    today = today or date.today()
    days = int(policy.get("visit_coupon_days") or 0)
    if days:
        return (today + timedelta(days=days)).isoformat()
    return date(today.year, 12, 31).isoformat()
