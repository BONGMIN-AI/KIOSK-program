"""발표 시연 목차를 만든다 (11/04 회의 2): 그림 없이 글자만, 시연하면서 보고 따라가기 좋게 단계마다 크게.

사용: python tools/build_demo_guides.py   → docs/release/시연설명/
  0_전체_진행표.html      팀장용: 네 사람 순서 · 단계 · 단계마다 할 설명
  1_김지성_시연.html …    팀원용: 자기 순서만 (할 일 → 화면에 나오면 성공 → 팀장 설명)
배포 ZIP과 회의 폴더(멤버별 시연 목차)에 넣는다 (tools/make_release.py).

시연 계정: 김휘원 withtop77 · 김지성 jisung0642 (비밀번호 1234, 얼굴은 미리 등록하지 않고 그 자리에서).
조민기는 그 자리에서 회원가입부터(아이디 asd1625), 임예찬은 비회원으로 예매표(임예찬 · 010-2007-2007).
"""
import html
from pathlib import Path

from build_manual import DOCS

OUT = DOCS / "시연설명"

STYLE = """
:root { --bg:#F7EEE3; --card:#FFFFFF; --brown:#3C1B03; --caramel:#B66B2E; --light:#F1DFCB; --line:#E6D6C4;
        --text2:#7A6252; --ok:#2E7D4F; --okbg:#E6F4EA; --say:#FBF5EE; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--brown); font-family:"Noto Sans KR","Malgun Gothic",sans-serif;
       font-size:19px; line-height:1.55; }
main { max-width:860px; margin:0 auto; padding:24px 16px 60px; }
header { background:var(--brown); color:#fff; border-radius:22px; padding:22px 26px; margin-bottom:18px; }
header h1 { margin:0; font-size:30px; } header p { margin:6px 0 0; color:#F1DFCB; font-size:18px; }
.who { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:16px 20px; margin-bottom:18px; }
.who b { color:var(--caramel); }
.part { font-size:24px; margin:28px 0 10px; padding-left:12px; border-left:6px solid var(--caramel); }
.step { display:grid; grid-template-columns:64px 1fr; gap:14px; background:var(--card); border:1px solid var(--line);
        border-radius:18px; padding:16px 18px; margin:12px 0; }
.num { width:56px; height:56px; border-radius:50%; background:var(--caramel); color:#fff; font-size:28px; font-weight:800;
       display:flex; align-items:center; justify-content:center; }
.todo { font-size:22px; font-weight:800; }
.see { margin-top:8px; background:var(--okbg); color:var(--ok); border-radius:10px; padding:8px 12px; font-weight:700; }
.see::before { content:"화면에 나오면 성공 ▸ "; font-weight:400; }
.say { margin-top:8px; background:var(--say); border-radius:10px; padding:8px 12px; color:var(--text2); }
.say::before { content:"팀장 설명 ▸ "; font-weight:700; color:var(--caramel); }
.gear { display:inline-block; margin-left:8px; background:var(--light); color:var(--brown); border-radius:999px;
        padding:2px 10px; font-size:15px; font-weight:700; vertical-align:middle; }
code { background:var(--light); border-radius:6px; padding:1px 8px; font-size:20px; }
.tip { background:var(--light); border-radius:14px; padding:12px 16px; margin:14px 0; font-size:17px; }
.toc { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:10px; }
.toc a { background:var(--card); border:1px solid var(--line); border-radius:999px; padding:6px 14px; color:var(--brown);
         text-decoration:none; font-weight:700; font-size:16px; }
@media print { body { background:#fff; } .step { break-inside:avoid; } }
"""

PAY = "<b>장바구니 확인 →</b> → <b>결제하기 →</b> → <b>결제로 이동 →</b> → 현금 버튼으로 돈 넣기 → <b>결제 완료</b>"

# (번호, 이름, 아이디 · 로그인, 맡은 기능, 단계 [(할 일, 화면에 나오면 성공, 팀장 설명, 장비)])
PARTS = [
    (1, "김지성", "jisung0642 · 비밀번호 1234 · 그 자리에서 얼굴 등록",
     "다가가면 시작 · 얼굴 등록 · 얼굴 로그인 · 버스표 구매 · 미소 미션 · 잔돈 포인트 · 새 칭호",
     [
         ("카메라에서 1m 밖에 서 있다가 키오스크로 천천히 다가가기", "가운데에 매장 / 포장 버튼 두 개가 스윽 떠오름",
          "화면을 누르지 않아도 손님이 다가오면 키오스크가 먼저 알아보고 주문을 시작해요.", "카메라"),
         ("<b>포장해 갈게요</b>", "시작 화면 (회원 주문 · 비회원 주문)", "주문을 시작하면 먼저 매장인지 포장인지 골라요.", ""),
         ("<b>회원 주문</b> → 아이디 <code>jisung0642</code> → <b>비밀번호로 로그인</b> → <code>1234</code> → "
          "<b>얼굴도 등록할게요</b> 체크 → <b>로그인 →</b>", "얼굴 등록 화면 (귀여운 라떼 얼굴)",
          "얼굴은 사진이 아니라 특징값만 암호화해서 저장해요. 처음 한 번만 등록하면 돼요.", "카메라"),
         ("카메라 50cm 안에서 정면을 보고 잠시 멈추기", "고리가 초록으로 차고 체크 → 메뉴 화면 · ‘… 김지성 님, 오늘 두 번째 방문이에요!’",
          "오늘 이미 왔던 것도 기억해서 인사가 달라져요.", "카메라"),
         ("<b>로그아웃</b> → <b>예, 로그아웃</b> → 1m 밖으로 물러났다가 다시 다가가기 → <b>포장해 갈게요</b>",
          "매장 / 포장 버튼이 다시 떠오름", "", "카메라"),
         ("<b>회원 주문</b> → 아이디 <code>jisung0642</code> → <b>얼굴 인증</b> → 정면 보기",
          "비밀번호 없이 로그인 · 메뉴 화면", "이제는 얼굴만 보면 로그인돼요. 사진을 들이대는 건 막아요.", "카메라"),
         ("<b>승차권</b> 탭 → <b>승차권 구매</b> → 출발지 그대로 · 도착지 <code>대전복합</code> · 날짜 → <b>검색 →</b>",
          "시간표 · 버스마다 ‘○석 남음’", "출발지 · 도착지 · 날짜를 고르면 남은 좌석과 요금이 나와요.", ""),
         ("버스 하나 → <b>다음 →</b> → 좌석 하나 누르기 → <b>다음 →</b>", "좌석이 빨갛게 · ‘5분 동안 잡아 둬요’",
          "고른 좌석은 5분 동안 다른 사람이 못 가져가요.", ""),
         ("승객 혜택에서 <b>경로</b> → <b>장바구니 담고 음료 고르기</b>", "승차권 금액이 할인되고 장바구니에 승차권",
          "경로 · 보훈 · 군인 · 장애인 할인을 고를 수 있어요.", ""),
         ("<b>디카페인</b> → <b>디카페인 아메리카노</b> → <b>장바구니 담기</b>", "장바구니에 버스표 + 음료",
          "커피와 버스표를 한 장바구니에 담아 한 번에 결제해요. 이게 우리 키오스크의 핵심이에요.", ""),
         ("<b>장바구니 확인 →</b> → <b>미소 미션</b> 체크 → 카메라 50cm 안에서 웃기",
          "‘카메라를 켜는 중이에요’ → 커피잔이 웃는 얼굴로 → ‘미소 미션 성공!’ −500원",
          "웃으면 500원 할인이에요. 웃은 시간이 3초 모이면 성공이고, 계정마다 한 번이에요.", "카메라"),
         ("<b>결제하기 →</b> → <b>결제로 이동 →</b> → 현금 넉넉히 (예: 10,000원 두 번) → "
          "<b>잔돈 … 포인트 적립</b> 체크 → <b>결제 완료</b>",
          "완료 화면 · 포장 · 승차장 · ‘★ 새 칭호 획득! [단골손님]’",
          "잔돈은 동전 대신 포인트로 쌓을 수 있어요. 주문이 쌓이면 새 칭호도 받아요.", ""),
         ("‘더 주문하시겠어요?’ → <b>아니요 · 끝내기</b>", "처음 화면", "", ""),
     ]),
    (2, "김휘원", "withtop77 · 비밀번호로 로그인 (얼굴 없이)",
     "비밀번호 로그인 · 인사와 칭호 · 생일 쿠폰 · 우유 알레르기 · 카페인 알리미 · 다시 담기 · 좋아요 · 저장한 노선 · 숨은 쿠폰",
     [
         ("대기 화면 누르기 → <b>매장에서 먹어요</b> → <b>회원 주문</b>", "회원 로그인 화면", "", ""),
         ("아이디 <code>withtop77</code> → <b>비밀번호로 로그인</b> → <code>1234</code> → <b>로그인 →</b>",
          "팝업 ‘생일 축하해요!’ · 위쪽 ‘[얼죽아] 김휘원 님, 2일 만이에요!’",
          "얼굴이 싫은 손님은 비밀번호로도 돼요. 생일을 기억해 축하 쿠폰을 주고, 마지막 방문일을 기억해 인사해요.", ""),
         ("팝업 <b>확인</b> → 위쪽 이름 <b>[얼죽아] 김휘원 님 ›</b> 누르기", "칭호 목록 · 다음 칭호까지 진행 막대",
          "주문 습관으로 칭호가 붙어요. 아이스 아메리카노를 자주 마셔서 ‘얼죽아’예요.", ""),
         ("닫고 <b>My Menu</b> → 최근 주문 <b>다시 담기 ▶</b>", "‘카페인 알리미 · 그래도 담을까요?’",
          "지난 주문을 버튼 하나로 다시 담아요. 이번 주 카페인 제한을 넘으면 한 번 물어봐요.", ""),
         ("<b>아니요</b> → 카페인 블록 오른쪽 위 <b>톱니바퀴</b> → <b>+</b> 두 번 → <b>완료</b>", "제한이 바로 늘고 ‘○잔 남았어요’",
          "손님이 이번 주 카페인 양을 직접 정해요. 잔 수로도 mg으로도 돼요.", ""),
         ("다시 <b>다시 담기 ▶</b>", "이번에는 바로 장바구니에 담김", "", ""),
         ("<b>커피</b> → <b>아메리카노</b> 누르기", "옵션 창에 ICE · L · 샷 추가가 미리 골라져 있음",
          "자주 시키던 옵션을 기억해서 미리 골라 줘요.", ""),
         ("옵션 창 닫기 → <b>커피</b> → <b>카페라떼</b> → <b>장바구니 담기</b>", "‘알레르기 주의 · 우유’",
          "가입할 때 적은 알레르기를 기억해서, 든 메뉴를 담으면 알려 줘요.", ""),
         ("<b>취소</b> → 음료 하나의 <b>♡</b> 누르기", "♥로 바뀌고 My Menu 좋아요에 들어감",
          "좋아하는 음료를 모아 둘 수 있어요 (최대 6잔).", ""),
         ("<b>My Menu</b> → ★ 저장한 노선 <b>서울경부 → 대전복합</b>", "승차권 탭의 오늘 시간표가 바로 열림",
          "자주 가는 노선은 저장해 두면 출발지 · 도착지를 안 골라도 돼요.", ""),
         ("메뉴 화면 왼쪽 위 <b>로고를 빠르게 5번</b>", "‘숨은 쿠폰을 찾았어요!’", "숨겨 둔 재미 요소예요.", ""),
         (PAY.replace("<b>결제로 이동 →</b>", "생일 쿠폰 고르기 → <b>결제로 이동 →</b>"), "쿠폰만큼 금액이 줄고 완료 화면",
          "", ""),
         ("<b>아니요 · 끝내기</b>", "처음 화면", "", ""),
     ]),
    (3, "조민기", "그 자리에서 회원가입 (아이디 asd1625 · 비밀번호 1234) · 얼굴 · 회원카드",
     "회원가입 · 얼굴 등록 · 회원카드 구매 → 처음 대서 등록 → 10% 할인 · 3% 적립 · 스탬프 → 카드로 로그인",
     [
         ("대기 화면 누르기 → <b>매장에서 먹어요</b> → <b>회원 주문</b> → 아래 <b>처음 오셨나요? 회원가입</b>",
          "회원가입 · 정보 입력", "", ""),
         ("이름 <code>조민기</code> · 아이디 <code>asd1625</code> · 비밀번호 <code>1234</code> 두 번 · "
          "전화번호 <code>01016251625</code>", "칸이 다 채워짐", "", ""),
         ("알레르기 하나 고르기 → <b>[필수] 개인정보</b> 체크 → <b>[선택] 얼굴 등록 동의</b> 체크 → "
          "<b>[선택] 회원카드 신청</b> 체크 → <b>다음 →</b>", "얼굴 등록 화면",
          "가입할 때 알레르기 · 얼굴 · 회원카드까지 한 번에 신청해요. 휴대폰으로 QR을 찍어 가입해도 돼요.", ""),
         ("카메라 50cm 안에서 정면 보기", "메뉴 화면 · 장바구니에 <b>회원카드 1,000원</b>", "", "카메라"),
         ("음료 하나 담기 → " + PAY, "완료 화면 · ‘회원카드는 음료와 함께 받아 가세요’",
          "카드는 음료 나올 때 같이 받아요. 처음 대기 전까지는 ‘등록 전’이에요.", ""),
         ("<b>아니요 · 끝내기</b> → 다시 <b>매장에서 먹어요</b> → <b>회원 주문</b> → <code>asd1625</code> → <b>얼굴 인증</b>",
          "‘받으신 회원카드를 리더기에 대면 등록돼요’ · My Menu 맨 위 <b>카드 등록</b>",
          "카드를 산 걸 기억하고 아직 등록 안 했다고 알려 줘요.", "카메라"),
         ("<b>카드 등록</b> → 받은 카드를 리더기에 대기", "팝업 ‘회원카드 등록 완료!’ (이번 주문 10% · 앞으로 3% 적립)",
          "처음 대면 카드 번호가 등록되고, 이번 주문은 10% 할인돼요.", "카드 리더기"),
         ("음료 하나 담기 → " + PAY, "쿠폰 · 포인트 화면에 ‘회원카드 첫 주문’ 할인 · 완료 화면에 스탬프 도장 1개",
          "카드로 주문할 때마다 도장이 하나씩. 10개 모으면 음료 한 잔이 무료예요.", ""),
         ("<b>아니요 · 끝내기</b> → 처음 화면에서 <b>카드만 리더기에 대기</b>",
          "‘조민기 님 카드 확인’ · 매장 / 포장 버튼", "다음부터는 카드만 대면 아이디를 안 쳐도 돼요.", "카드 리더기"),
         ("<b>매장에서 먹어요</b> → 카메라 보기", "얼굴로 바로 로그인 · 메뉴 화면", "카드 + 얼굴로 아무것도 안 치고 로그인해요.", "카메라"),
         ("<b>로그아웃</b> → <b>예, 로그아웃</b>", "처음 화면", "", ""),
     ]),
    (4, "임예찬", "비회원 (아이디 없음)",
     "예매표 출력 (이름 + 휴대폰 번호) · 비회원 주문 · 예매표 0원 · 커피와 함께 결제",
     [
         ("대기 화면 누르기 → <b>매장에서 먹어요</b> → <b>비회원 주문</b>", "메뉴 화면 · 위쪽 ‘비회원 주문’",
          "회원이 아니어도 바로 주문할 수 있어요.", ""),
         ("<b>승차권</b> 탭 → <b>예매표 출력</b>", "예매표 출력 · 조회 (이름 + 휴대폰 번호)", "", ""),
         ("이름 <code>임예찬</code> · 휴대폰 번호 <code>01020072007</code> → <b>조회</b>", "예매한 표 2장 · 출발까지 남은 시간",
          "인터넷이나 앱으로 예매한 표를 이름과 휴대폰 번호로 찾아요. 예매번호로도 돼요.", ""),
         ("뒤의 표를 눌러 체크를 빼고 → <b>장바구니에 담기</b>", "‘장바구니에 담았어요 · ○번 승차장’ · 장바구니에 예매표 0원",
          "이미 돈을 낸 표라서 0원으로 담겨요. 결제를 마치면 출력돼요.", ""),
         ("<b>음료 고르기 →</b> → <b>커피</b>에서 하나 → <b>장바구니 담기</b>", "장바구니에 예매표 + 음료",
          "표를 받으면서 커피도 같이 사요.", ""),
         ("<b>장바구니 확인 →</b> → <b>결제하기 →</b> → 돈 넣기 → <b>투입 취소 · 반환</b>", "넣은 현금이 그대로 돌아옴",
          "잘못 넣었으면 언제든 돌려받을 수 있어요.", ""),
         ("다시 돈 넣기 → <b>결제 완료</b>", "완료 화면 · 대기 번호 · 승차권 정보", "비회원은 대기 번호로 불러요.", ""),
         ("<b>아니요 · 끝내기</b> → <b>비회원 주문</b> → <b>승차권</b> → <b>예매표 출력</b> → 같은 이름 · 번호로 조회",
          "방금 받은 표는 빠지고 1장만 나옴", "한 번 출력한 표는 다시 출력되지 않아요.", ""),
         ("<b>처음으로</b>", "처음 화면", "", ""),
     ]),
]


def step_html(number, todo, see, say, gear):
    todo = todo.replace(" →</b> →", "</b> →")              # '확인 →' 뒤에 또 → 가 붙지 않게
    tag = f'<span class="gear">{gear}</span>' if gear else ""
    body = f'<div class="step"><div class="num">{number}</div><div><div class="todo">{todo}{tag}</div>'
    if see:
        body += f'<div class="see">{see}</div>'
    if say:
        body += f'<div class="say">{html.escape(say)}</div>'
    return body + "</div></div>"


def part_html(order, name, login, features, steps, leader=False):
    rows = "".join(step_html(i, *s) for i, s in enumerate(steps, 1))
    return (f'<h2 class="part" id="p{order}">{order}. {name}</h2>'
            f'<div class="who"><b>로그인</b> {login}<br><b>보여 줄 것</b> {features}</div>{rows}')


def document(title, sub, body):
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>"
            f"<header><h1>{title}</h1><p>{sub}</p></header>{body}</main></body></html>")


COMMON = ('<div class="tip"><b>켜기</b>: 팀장 노트북에서 시연 모드 (카메라 · 카드 리더 연결). 순서대로 이어서 해요 '
          '(앞 사람이 가입한 회원 · 등록한 얼굴이 그대로 남아 있어야 해요 · 중간에 프로그램을 끄지 않기).<br>'
          '꼬였으면 <b>처음으로</b> / <b>로그아웃</b> → 그 단계부터 다시. 비밀번호는 모두 <code>1234</code>.</div>')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.html"):             # 예전(그림 있는) 설명은 지운다 (이 도구가 만든 것)
        old.unlink()
    toc = '<div class="toc">' + "".join(f'<a href="#p{o}">{o}. {n}</a>' for o, n, *_ in PARTS) + "</div>"
    whole = "".join(part_html(*part) for part in PARTS)
    (OUT / "0_전체_진행표.html").write_text(
        document("발표 시연 전체 진행표 (팀장용)", "팀원이 단계별로 누르는 동안 팀장이 ‘팀장 설명’을 말해요", toc + COMMON + whole),
        encoding="utf-8")
    for order, name, login, features, steps in PARTS:
        (OUT / f"{order}_{name}_시연.html").write_text(
            document(f"{order}. {name} 시연", f"{features}", COMMON + part_html(order, name, login, features, steps)),
            encoding="utf-8")
    print(f"시연 목차 {len(PARTS) + 1}개를 만들었습니다 → {OUT}")


if __name__ == "__main__":
    main()
