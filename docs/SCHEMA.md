# KIOSK 데이터 스키마

모든 데이터는 실행 중에는 파이썬 딕셔너리·리스트이고, 저장할 때 JSON으로 바꾼 뒤
Fernet으로 암호화한다. 디스크에는 `data/<이름>.json.enc`만 남는다.

| 데이터셋 | 키 예시 | 핵심 내용 |
|---|---|---|
| `menu` | `M001` | 이름, 분류, 가격, 알레르기, 재고, 판매 수, 품절 |
| `customers` | `C0001` | 회원 ID, 비밀번호 해시, 이름, 전화번호, 닉네임, 얼굴 등록 여부, 동의, 알레르기, 포인트, 쿠폰(`{id,name,amount,min_order,expires}`), 방문 수, `point_history`(최근 50건: 시각·변동·잔액·사유·처리자), `preferences`(언어·고대비·큰 글자) |
| `orders` | `O0001` | 주문 항목(옵션 포함), 총액, 쿠폰·포인트 할인, 결제액, 현금, 거스름돈·단위, 적립 포인트·적용 이벤트, 회원 스냅샷, 상태, 시각 |
| `settings` | 고정 키 | 가게 이름, 다음 주문번호, 손님 화면 기본값(`language`·`high_contrast`·`large_mode`), `point_policy`(적립·사용·방문 쿠폰·기간 이벤트 — `domain/policy.py` 설명 참고) |
| `face_profiles` | `C0001` | SFace 특징값, 알고리즘, 등록 시각, 생체 확인 방식 |

회원 공통 필드는 `id`, `name`, `phone`, `created_at`, `updated_at`, `extra`다.
도메인 전용 값은 `extra` 안에 넣는다.

회원 비밀번호는 원문을 저장하지 않고 회원별 salt가 포함된 PBKDF2 해시로 저장한다.
얼굴 사진과 카메라 프레임은 저장하지 않는다. 회원 카드에는 `face_enrolled` 여부만 두고,
SFace가 만든 128차원 특징값은 별도 `face_profiles` 데이터셋에 넣은 뒤 Vault로 암호화한다.

```text
관리자 비밀번호 → PBKDF2 → 키 암호화 키(KEK)
                                ↓
                         데이터 키(DK) 해제
                                ↓
menu/customers/orders/settings JSON 암호화·복호화
```

SQLite는 이번 BASE에 필요하지 않다. 주문이 매우 많아져 복잡한 검색·집계나 여러 기기의
동시 접근이 필요할 때 확장 후보로만 둔다.

운영자 행동(로그인, 메뉴·정책·이벤트 변경, 포인트 조정, 종료)은 `data/audit.log`에 해시 체인으로 남는다.
개인정보 없이 운영자 ID·행동·대상 ID만 기록하며, 운영자 화면 `감사 로그`에서 변조 여부를 검사한다.
