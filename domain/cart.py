"""장바구니 계산. 파일이나 화면에 접근하지 않는 순수 함수만 둔다.

장바구니 한 줄 = {"menu_id": ..., "options": {...}, "quantity": n}
키는 options.line_key()로 만들어 같은 메뉴라도 옵션이 다르면 다른 줄이 된다.
옛 형식({"M001": 2})도 그대로 읽을 수 있다.
"""
from .options import line_key, normalize_options, option_label, option_price

MAX_QUANTITY = 10


def _entry(key: str, value) -> dict:
    if isinstance(value, int):
        return {"menu_id": key, "options": {}, "quantity": value}
    return value


def add_item(cart: dict, menu_id: str, quantity: int = 1, options: dict | None = None,
             menu: dict | None = None) -> dict:
    if quantity < 1:
        raise ValueError("수량은 1개 이상이어야 합니다")
    if menu is not None:
        if menu_id not in menu:
            raise ValueError(f"없는 메뉴입니다: {menu_id}")
        options = normalize_options(menu[menu_id], options)
    options = options or {}
    key = line_key(menu_id, options)
    updated = dict(cart)
    current = _entry(key, updated[key])["quantity"] if key in updated else 0
    if current + quantity > MAX_QUANTITY:
        raise ValueError(f"한 메뉴는 최대 {MAX_QUANTITY}개까지 담을 수 있습니다")
    updated[key] = {"menu_id": menu_id, "options": options, "quantity": current + quantity}
    return updated


def change_quantity(cart: dict, key: str, quantity: int) -> dict:
    updated = dict(cart)
    if quantity <= 0:
        updated.pop(key, None)
    else:
        if quantity > MAX_QUANTITY:
            raise ValueError(f"한 메뉴는 최대 {MAX_QUANTITY}개까지 담을 수 있습니다")
        entry = dict(_entry(key, updated[key]))
        entry["quantity"] = quantity
        updated[key] = entry
    return updated


def cart_lines(cart: dict, menu: dict) -> list[dict]:
    lines = []
    needed = {}
    for key, value in cart.items():
        entry = _entry(key, value)
        menu_id = entry["menu_id"]
        if menu_id not in menu:
            raise ValueError(f"없는 메뉴입니다: {menu_id}")
        needed[menu_id] = needed.get(menu_id, 0) + entry["quantity"]
        item = menu[menu_id]
        unit_price = item["price"] + option_price(entry["options"])
        lines.append({
            "key": key,
            "menu_id": menu_id,
            "name": item["name"],
            "options": entry["options"],
            "option_label": option_label(entry["options"]),
            "quantity": entry["quantity"],
            "unit_price": unit_price,
            "subtotal": unit_price * entry["quantity"],
        })
    # 옵션이 달라도 재고는 같은 메뉴끼리 합쳐서 확인한다.
    for menu_id, quantity in needed.items():
        item = menu[menu_id]
        if item.get("sold_out") or item.get("stock", 0) < quantity:
            raise ValueError(f"재고가 부족합니다: {item['name']} (남은 수량 {item.get('stock', 0)}개)")
    return lines


def total_price(cart: dict, menu: dict) -> int:
    return sum(line["subtotal"] for line in cart_lines(cart, menu))
