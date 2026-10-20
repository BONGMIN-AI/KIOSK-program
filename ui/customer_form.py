"""B 담당 예시: 금고(vault)를 '받아서' 쓰는 방법."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 프로젝트 폴더를 찾게 해 줌

from core.storage import MemoryVault          # 연습용 가짜 금고
from core.validators import normalize_phone   # 전화번호 변환
from core import schema                       # 고객 카드 만드는 도구


def save_customer(vault, name, phone_text):
    """화면에서 받은 이름/전화번호를 금고에 저장한다. 금고는 직접 만들지 않고 받아서 쓴다."""
    phone = normalize_phone(phone_text)            # 잘못된 번호면 ValueError
    customers = vault.read("customers", default={})   # 금고에서 꺼내기
    new_id = schema.next_id("C", customers)
    customers[new_id] = schema.new_record(new_id, name, phone, points=0)
    vault.write("customers", customers)            # 금고에 넣기
    return new_id


if __name__ == "__main__":
    vault = MemoryVault()                  # 연습할 때는 가짜 금고
    print(save_customer(vault, "홍길동", "01012345678"))
    print(vault.read("customers"))
