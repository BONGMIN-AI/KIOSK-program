"""현금 결제 계산."""

DENOMINATIONS = (50000, 10000, 5000, 1000, 500, 100, 50, 10)
DENOMINATION_NAMES = {50000: "오만원권", 10000: "만원권", 5000: "오천원권", 1000: "천원권",
                      500: "500원", 100: "100원", 50: "50원", 10: "10원", 1: "1원"}


def insert_cash(inserted: int, amount: int) -> int:
    """현금을 한 번 더 넣는다. 지금까지 넣은 금액에 더해 돌려준다."""
    if amount <= 0:
        raise ValueError("넣은 금액을 1원 이상으로 입력하세요")
    if amount % 10:
        raise ValueError("현금은 10원 단위로 넣을 수 있습니다")
    return inserted + amount


def payment_status(total: int, cash: int) -> dict:
    if total < 0 or cash < 0:
        raise ValueError("금액은 0원 이상이어야 합니다")
    shortage = max(total - cash, 0)
    change = max(cash - total, 0)
    return {
        "paid": shortage == 0,
        "total": total,
        "cash": cash,
        "shortage": shortage,
        "change": change,
        "breakdown": change_breakdown(change),
    }


def change_breakdown(amount: int) -> dict[int, int]:
    if amount < 0:
        raise ValueError("거스름돈은 0원 이상이어야 합니다")
    result = {}
    remaining = amount
    for unit in DENOMINATIONS:
        count, remaining = divmod(remaining, unit)
        if count:
            result[unit] = count
    if remaining:
        result[1] = remaining
    return result


def coin_tip(shortage: int) -> str | None:
    """동전 최소화 안내 (C-6). 남은 금액의 천 원 아래 부분을 동전으로 먼저 넣으면 거스름돈이 지폐로만 나온다.

    예) 4,500원 남음 → "500원을 동전으로 같이 넣으면 거스름돈에 동전이 없어요". 딱 천 원 단위면 None.
    """
    coins = shortage % 1000
    if shortage <= 0 or coins == 0:
        return None
    return f"{coins:,}원을 동전으로 같이 넣으면 거스름돈에 동전이 없어요"


def breakdown_text(breakdown: dict) -> str:
    """{1000: 4, 500: 1} -> '천원권 4장 · 500원 1개'"""
    if not breakdown:
        return "거스름돈 없음"
    parts = []
    for unit, count in sorted(breakdown.items(), key=lambda pair: -int(pair[0])):
        unit = int(unit)
        word = "장" if unit >= 1000 else "개"
        parts.append(f"{DENOMINATION_NAMES[unit]} {count}{word}")
    return " · ".join(parts)
