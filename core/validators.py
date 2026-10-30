"""입력 검증. 순수 함수만 둔다 (파일, 화면 접근 금지)."""
import re


def normalize_phone(raw: str) -> str:
    """'01012345678', '010 1234 5678', '+82 10-1234-5678' -> '010-1234-5678'. 안 맞으면 ValueError."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("82"):
        digits = "0" + digits[2:]
    if not re.fullmatch(r"010\d{8}", digits):
        raise ValueError("전화번호는 010-xxxx-xxxx 형식이어야 합니다")
    return f"010-{digits[3:7]}-{digits[7:]}"


def format_phone_typing(raw: str) -> str:
    """입력하는 동안 보여 줄 모양: 숫자만 남기고 '010-1234-5678'처럼 하이픈을 넣는다 (최대 11자리)."""
    digits = re.sub(r"\D", "", raw or "")[:11]
    if len(digits) <= 3:
        return digits
    if len(digits) <= 7:
        return f"{digits[:3]}-{digits[3:]}"
    return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"


def mask_phone(phone: str) -> str:
    """010-1234-5678 -> 010-****-5678"""
    return f"{phone[:4]}****{phone[8:]}"
