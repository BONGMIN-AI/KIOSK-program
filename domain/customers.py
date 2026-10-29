"""회원 데이터 카드 생성과 ID·얼굴·비밀번호 인증."""
import base64
import hashlib
import hmac
import os
import re

from core import schema
from core.validators import normalize_phone
from .allergens import normalize, normalize_all

MEMBER_PASSWORD_ITERATIONS = 120_000


def normalize_login_id(raw: str) -> str:
    login_id = (raw or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{4,20}", login_id):
        raise ValueError("회원 ID는 영문 소문자·숫자·_ 조합 4~20자로 입력하세요")
    return login_id


def hash_member_password(password: str, salt: bytes | None = None,
                         iterations: int = MEMBER_PASSWORD_ITERATIONS) -> dict:
    if len(password or "") < 4:
        raise ValueError("회원 비밀번호는 4자 이상이어야 합니다")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "iterations": iterations,
        "digest": base64.b64encode(digest).decode("ascii"),
    }


def verify_member_password(password: str, stored: dict) -> bool:
    salt = base64.b64decode(stored["salt"])
    expected = base64.b64decode(stored["digest"])
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, int(stored["iterations"])
    )
    return hmac.compare_digest(actual, expected)


def validate_password_pair(password: str, confirm: str) -> None:
    """회원가입 때 비밀번호와 재입력이 같은지 확인한다."""
    if len(password or "") < 4:
        raise ValueError("회원 비밀번호는 4자 이상이어야 합니다")
    if password != confirm:
        raise ValueError("비밀번호와 비밀번호 재입력이 다릅니다")


def register_customer(vault, name: str, nickname: str, phone: str,
                      login_id: str, password: str,
                      birthday: str = "", allergies=None,
                      privacy_agreed: bool = False,
                      marketing_agreed: bool = False,
                      face_enrolled: bool = False) -> dict:
    if not name.strip():
        raise ValueError("이름을 입력하세요")
    nickname = (nickname or "").strip() or name.strip()  # 닉네임을 따로 받지 않으면 이름을 대기 명단에 쓴다
    if not privacy_agreed:
        raise ValueError("필수 개인정보 활용 동의가 필요합니다")
    phone = normalize_phone(phone)
    login_id = normalize_login_id(login_id)
    customers = vault.read("customers", default={})
    if any(record["phone"] == phone for record in customers.values()):
        raise ValueError("이미 등록된 전화번호입니다")
    if any(record.get("extra", {}).get("login_id") == login_id for record in customers.values()):
        raise ValueError("이미 사용 중인 회원 ID입니다")
    customer_id = schema.next_id("C", customers)
    record = schema.new_record(
        customer_id, name.strip(), phone,
        nickname=nickname.strip(), login_id=login_id,
        password_hash=hash_member_password(password), birthday=birthday.strip(),
        allergies=normalize_all(allergies), privacy_agreed=True,
        marketing_agreed=bool(marketing_agreed),
        face_enrolled=bool(face_enrolled), points=0, coupons=[], visits=0,
    )
    customers[customer_id] = record
    vault.write("customers", customers)
    return record


def find_by_phone(vault, phone: str):
    normalized = normalize_phone(phone)
    customers = vault.read("customers", default={})
    return next((record for record in customers.values() if record["phone"] == normalized), None)


def find_by_login_id(vault, login_id: str):
    login_id = normalize_login_id(login_id)
    customers = vault.read("customers", default={})
    return next((record for record in customers.values()
                 if record.get("extra", {}).get("login_id") == login_id), None)


def login_with_password(vault, login_id: str, password: str):
    customer = find_by_login_id(vault, login_id)
    if not customer or not verify_member_password(password, customer["extra"]["password_hash"]):
        raise ValueError("회원 ID 또는 비밀번호가 올바르지 않습니다")
    reset_face_failures(vault, customer["id"])    # 본인이 비밀번호로 확인했으니 얼굴 잠금을 푼다
    return customer


def card_hash(card_id: str) -> str:
    """RFID 카드 번호는 그대로 두지 않고 해시로만 회원 카드에 적는다 (금고 안에서도)."""
    card_id = (card_id or "").strip()
    if len(card_id) < 4:
        raise ValueError("카드 번호를 읽지 못했어요. 다시 대 주세요")
    return hashlib.sha256(f"coffee-spoon-card:{card_id}".encode("utf-8")).hexdigest()


def find_by_card(vault, card_id: str):
    digest = card_hash(card_id)
    customers = vault.read("customers", default={})
    return next((record for record in customers.values()
                 if record.get("extra", {}).get("card_hash") == digest), None)


def link_card(vault, customer_id: str, card_id: str) -> dict:
    """회원 카드(RFID)를 이 회원에게 연결한다. 다른 회원이 쓰는 카드면 거절, 예전 카드는 바뀐다."""
    digest = card_hash(card_id)
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("회원을 찾을 수 없어요")
    owner = next((key for key, record in customers.items()
                  if record.get("extra", {}).get("card_hash") == digest), None)
    if owner and owner != customer_id:
        raise ValueError("이미 다른 회원에게 연결된 카드예요")
    record = customers[customer_id]
    record["extra"]["card_hash"] = digest
    schema.touch(record)
    vault.write("customers", customers)
    return record


RESET_FAILURES = "reset_failures"   # {회원 ID 또는 'phone:번호': 본인 확인 연속 실패 횟수}
MAX_RESET_FAILURES = 5


def mask_login_id(login_id: str) -> str:
    """kbm000608 -> kbm****08 (앞 3자·뒤 2자만 보여 준다)."""
    if len(login_id) <= 5:
        return login_id[:2] + "*" * (len(login_id) - 2)
    return login_id[:3] + "*" * (len(login_id) - 5) + login_id[-2:]


def _check_reset_lock(vault, key: str) -> None:
    if vault.read(RESET_FAILURES, default={}).get(key, 0) >= MAX_RESET_FAILURES:
        raise ValueError(f"본인 확인을 {MAX_RESET_FAILURES}번 틀려 잠겼어요. 직원을 불러 주세요")


def _reset_failed(vault, key: str) -> None:
    failures = vault.read(RESET_FAILURES, default={})
    failures[key] = failures.get(key, 0) + 1
    vault.write(RESET_FAILURES, failures)


def _reset_passed(vault, key: str) -> None:
    failures = vault.read(RESET_FAILURES, default={})
    if failures.pop(key, None) is not None:
        vault.write(RESET_FAILURES, failures)


def find_login_id(vault, phone: str) -> str:
    """아이디 찾기: 가입한 전화번호로 가린 아이디를 돌려준다 (화면 키보드는 영문·숫자뿐이라 이름 대신 전화번호)."""
    normalized = normalize_phone(phone)
    key = f"phone:{normalized}"
    _check_reset_lock(vault, key)
    customer = find_by_phone(vault, normalized)
    if not customer or not customer["extra"].get("login_id"):
        _reset_failed(vault, key)
        raise ValueError("이 전화번호로 가입한 회원이 없어요")
    _reset_passed(vault, key)
    return mask_login_id(customer["extra"]["login_id"])


def verify_identity(vault, login_id: str, phone: str):
    """비밀번호 재설정 전 본인 확인: 아이디와 전화번호가 같은 회원인지. 5번 틀리면 잠근다."""
    login_id = normalize_login_id(login_id)
    _check_reset_lock(vault, login_id)
    customer = find_by_login_id(vault, login_id)
    try:
        matched = customer is not None and customer["phone"] == normalize_phone(phone)
    except ValueError:
        matched = False
    if not matched:
        _reset_failed(vault, login_id)
        left = MAX_RESET_FAILURES - vault.read(RESET_FAILURES, default={}).get(login_id, 0)
        raise ValueError(f"아이디와 전화번호가 맞지 않아요 ({left}번 더 틀리면 잠겨요)" if left > 0
                         else "아이디와 전화번호가 맞지 않아 잠겼어요. 직원을 불러 주세요")
    _reset_passed(vault, login_id)
    return customer


def reset_member_password(vault, customer_id: str, password: str, confirm: str) -> dict:
    """본인 확인을 마친 회원의 비밀번호를 새로 정한다. 얼굴 로그인 잠금도 함께 푼다."""
    validate_password_pair(password, confirm)
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("회원을 찾을 수 없어요")
    record = customers[customer_id]
    record["extra"]["password_hash"] = hash_member_password(password)
    schema.touch(record)
    vault.write("customers", customers)
    reset_face_failures(vault, customer_id)
    return record


FACE_FAILURES = "face_failures"   # {회원 ID: 얼굴 로그인 연속 실패 횟수}
MAX_FACE_FAILURES = 3


def face_locked(vault, customer_id: str) -> bool:
    return vault.read(FACE_FAILURES, default={}).get(customer_id, 0) >= MAX_FACE_FAILURES


def reset_face_failures(vault, customer_id: str) -> None:
    failures = vault.read(FACE_FAILURES, default={})
    if failures.pop(customer_id, None) is not None:
        vault.write(FACE_FAILURES, failures)


def _add_face_failure(vault, customer_id: str) -> int:
    failures = vault.read(FACE_FAILURES, default={})
    failures[customer_id] = failures.get(customer_id, 0) + 1
    vault.write(FACE_FAILURES, failures)
    return failures[customer_id]


def login_with_face(vault, login_id: str, face_provider, on_status=print):
    """얼굴 불일치·사진 판정이 3번 이어지면 얼굴 로그인을 잠근다. 비밀번호로 로그인하면 풀린다."""
    from face import SpoofError
    customer = find_by_login_id(vault, login_id)
    if not customer:
        raise ValueError("등록된 회원 ID가 없습니다")
    if not customer["extra"].get("face_enrolled"):
        raise ValueError("이 회원은 얼굴 정보가 없습니다. 비밀번호를 사용하세요")
    if face_locked(vault, customer["id"]):
        raise ValueError(f"얼굴 로그인이 {MAX_FACE_FAILURES}번 실패해 잠겼어요. 비밀번호로 로그인하면 풀려요")
    try:
        matched_id = face_provider.identify_face(customer["id"], on_status)
    except SpoofError:
        _add_face_failure(vault, customer["id"])
        raise
    if matched_id != customer["id"]:
        count = _add_face_failure(vault, customer["id"])
        left = MAX_FACE_FAILURES - count
        tail = f"{left}번 더 틀리면 얼굴 로그인이 잠겨요" if left > 0 else "얼굴 로그인이 잠겼어요"
        raise ValueError(f"얼굴이 일치하지 않습니다 ({tail}). 비밀번호를 사용하세요")
    reset_face_failures(vault, customer["id"])
    return customer


def set_face_enrolled(vault, customer_id: str, enrolled: bool = True) -> dict:
    """얼굴 특징 저장 성공 뒤에만 회원 카드의 등록 상태를 바꾼다."""
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("등록 상태를 바꿀 회원이 없습니다")
    record = customers[customer_id]
    record["extra"]["face_enrolled"] = bool(enrolled)
    schema.touch(record)
    vault.write("customers", customers)
    reset_face_failures(vault, customer_id)
    return record


POINT_HISTORY_LIMIT = 50


def add_point_history(customer: dict, delta: int, reason: str, actor: str) -> None:
    """회원 카드에 포인트 변동 기록을 남긴다. 최근 50건만 보관한다."""
    history = customer["extra"].setdefault("point_history", [])
    history.append({"at": schema.now_iso(), "delta": int(delta), "reason": reason,
                    "by": actor, "balance": customer["extra"]["points"]})
    del history[:-POINT_HISTORY_LIMIT]


def adjust_points(vault, customer_id: str, delta: int, reason: str, actor: str) -> dict:
    """운영자가 결제 후 포인트를 직접 더하거나 뺀다. 사유는 반드시 남긴다."""
    delta = int(delta)
    reason = (reason or "").strip()
    if delta == 0:
        raise ValueError("조정할 포인트를 0이 아닌 값으로 입력하세요 (빼려면 -500 처럼)")
    if not reason:
        raise ValueError("포인트 조정 사유를 입력하세요")
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("포인트를 조정할 회원이 없습니다")
    record = customers[customer_id]
    new_balance = record["extra"]["points"] + delta
    if new_balance < 0:
        raise ValueError(f"포인트가 0보다 작아질 수 없습니다 (현재 {record['extra']['points']:,}P)")
    record["extra"]["points"] = new_balance
    add_point_history(record, delta, f"운영자 조정: {reason}", actor)
    schema.touch(record)
    vault.write("customers", customers)
    return record


def save_preferences(vault, customer_id: str, preferences: dict) -> dict:
    """회원 카드에 언어·고대비·큰 글자 설정을 저장한다. 다음 로그인 때 자동으로 적용된다."""
    allowed = {"language", "high_contrast", "large_mode"}
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("설정을 저장할 회원이 없습니다")
    record = customers[customer_id]
    current = record["extra"].get("preferences", {})
    record["extra"]["preferences"] = {**current, **{k: v for k, v in preferences.items() if k in allowed}}
    schema.touch(record)
    vault.write("customers", customers)
    return record


def allergy_warnings(customer: dict | None, lines: list[dict], menu: dict) -> list[str]:
    if not customer:
        return []
    allergies = set(normalize_all(customer.get("extra", {}).get("allergies", [])))
    warnings = []
    for line in lines:
        matched = allergies.intersection(normalize(a) for a in menu[line["menu_id"]].get("allergens", []))
        if matched:
            warnings.append(f"{line['name']}: {', '.join(sorted(matched))}")
    return warnings
