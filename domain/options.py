"""메뉴 옵션 규칙. 와이어프레임 04 옵션 팝업(온도·사이즈·샷·시럽)과 같은 기준을 쓴다."""

DRINK_CATEGORIES = ("커피", "디카페인", "논커피", "차", "에이드")
SIZE_PRICES = {"M": 0, "L": 1000}
EXTRA_PRICES = {"shot": 500, "syrup": 500}
EXTRA_LABELS = {"shot": "샷 1회 추가", "syrup": "시럽 추가"}


def available_options(item: dict) -> dict:
    """메뉴 하나에서 고를 수 있는 옵션 목록. 디저트는 옵션이 없다."""
    category = item.get("category")
    if category not in DRINK_CATEGORIES:
        return {"temperatures": [], "sizes": [], "extras": []}
    temperatures = ["ICE"] if category == "에이드" else ["HOT", "ICE"]
    extras = ["shot", "syrup"] if category in ("커피", "디카페인") else ["syrup"]
    return {"temperatures": temperatures, "sizes": list(SIZE_PRICES), "extras": extras}


def normalize_options(item: dict, options: dict | None) -> dict:
    """화면에서 받은 선택값을 검사하고, 빠진 값은 기본값으로 채운다."""
    rules = available_options(item)
    options = dict(options or {})
    if not rules["temperatures"]:
        if any(options.get(key) for key in ("temperature", "size", "extras")):
            raise ValueError(f"{item['name']}은(는) 옵션을 고를 수 없는 메뉴입니다")
        return {}
    temperature = options.get("temperature") or rules["temperatures"][-1]
    size = options.get("size") or "M"
    extras = sorted(set(options.get("extras") or []))
    if temperature not in rules["temperatures"]:
        raise ValueError(f"{item['name']}은(는) {temperature}로 주문할 수 없습니다")
    if size not in rules["sizes"]:
        raise ValueError("사이즈는 M 또는 L만 고를 수 있습니다")
    for extra in extras:
        if extra not in rules["extras"]:
            raise ValueError(f"{item['name']}에는 {EXTRA_LABELS.get(extra, extra)}을(를) 고를 수 없습니다")
    return {"temperature": temperature, "size": size, "extras": extras}


def option_price(options: dict) -> int:
    if not options:
        return 0
    return SIZE_PRICES[options["size"]] + sum(EXTRA_PRICES[extra] for extra in options["extras"])


def option_label(options: dict) -> str:
    """'ICE / L / 샷 1회 추가' 형태의 짧은 설명."""
    if not options:
        return ""
    parts = [options["temperature"], options["size"]]
    parts += [EXTRA_LABELS[extra] for extra in options["extras"]]
    return " / ".join(parts)


def line_key(menu_id: str, options: dict) -> str:
    """같은 메뉴라도 옵션이 다르면 장바구니에서 다른 줄로 본다."""
    if not options:
        return menu_id
    return "|".join([menu_id, options["temperature"], options["size"], *options["extras"]])
