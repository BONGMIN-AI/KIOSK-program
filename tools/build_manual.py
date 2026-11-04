"""사용 설명서와 시연 테스트 체크리스트 HTML을 만든다 (그림은 파일 안에 넣어 어디서 열어도 보이게).

사용: python tools/capture_manual.py   (화면 그림 새로 찍기)
      python tools/build_manual.py     → docs/release/사용설명서.html · docs/release/시연_테스트_체크리스트.html
"""
import base64
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "release"
IMAGES = DOCS / "images"

STYLE = """
:root { --bg:#F7EEE3; --card:#FFFFFF; --brown:#3C1B03; --text2:#7A6252; --caramel:#B66B2E; --cream:#FBF6EF;
        --accent:#D4573C; --line:#E8D9C6; --ok:#2E7D4F; --okbg:#E3F3E8; --bad:#C0392B; --badbg:#FBE3DF; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#1E1712; --card:#2A211A; --brown:#F3E6D8;
        --text2:#C9B5A2; --cream:#33281F; --line:#4A3B2E; --okbg:#1F3A2A; --badbg:#3E2320; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--brown); font:17px/1.75 "Malgun Gothic","Apple SD Gothic Neo",sans-serif; }
header { background:#3C1B03; color:#fff; padding:34px 16px 30px; text-align:center; }
header h1 { margin:0 0 6px; font-size:30px; }
header p { margin:0; opacity:.85; }
main { max-width:1000px; margin:0 auto; padding:22px 16px 60px; }
nav, section { background:var(--card); border-radius:18px; padding:20px 24px; margin-bottom:20px;
               box-shadow:0 4px 18px rgba(60,27,3,.06); }
nav ol { margin:6px 0 0; padding-left:22px; columns:2; }
nav a { color:var(--caramel); text-decoration:none; }
h2 { margin:0 0 12px; font-size:24px; }
h3 { margin:22px 0 8px; font-size:19px; }
p { margin:8px 0; }
ul, ol { padding-left:22px; margin:8px 0; }
li { margin:4px 0; }
.steps { counter-reset:s; list-style:none; padding:0; }
.steps > li { counter-increment:s; position:relative; padding:2px 0 10px 46px; }
.steps > li::before { content:counter(s); position:absolute; left:0; top:2px; width:32px; height:32px; border-radius:50%;
                      background:var(--caramel); color:#fff; font-weight:700; text-align:center; line-height:32px; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
figure { margin:10px 0 14px; }
figure img { width:100%; border-radius:12px; border:1px solid var(--line); display:block; }
figcaption { color:var(--text2); font-size:14px; margin-top:6px; }
.tip { background:var(--cream); border-left:5px solid var(--caramel); padding:10px 16px; border-radius:10px; margin:12px 0; }
.warn { background:var(--badbg); border-left:5px solid var(--accent); padding:10px 16px; border-radius:10px; margin:12px 0; }
table { width:100%; border-collapse:collapse; margin:10px 0; }
th, td { border-bottom:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }
th { background:var(--cream); }
code, kbd { background:var(--cream); border:1px solid var(--line); border-radius:6px; padding:1px 6px;
            font-family:Consolas,monospace; font-size:15px; }
.flow { display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
.flow span { background:var(--cream); border:1px solid var(--line); border-radius:999px; padding:4px 12px; font-size:15px; }
.flow b { color:var(--caramel); }
@media (max-width:700px) { nav ol { columns:1; } .grid { grid-template-columns:1fr; } }
"""


def image(name, caption):
    data = base64.b64encode((IMAGES / f"{name}.jpg").read_bytes()).decode("ascii")
    return (f'<figure><img src="data:image/jpeg;base64,{data}" alt="{html.escape(caption)}">'
            f"<figcaption>{caption}</figcaption></figure>")


def grid(*figures):
    return '<div class="grid">' + "".join(figures) + "</div>"


def steps(*items):
    return '<ol class="steps">' + "".join(f"<li>{item}</li>" for item in items) + "</ol>"


def bullets(*items):
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def flow(*parts):
    return '<div class="flow">' + " <b>→</b> ".join(f"<span>{part}</span>" for part in parts) + "</div>"


def section(anchor, title, body):
    return f'<section id="{anchor}"><h2>{title}</h2>{body}</section>'


def manual():
    parts = []
    parts.append(section("about", "1. 이 키오스크는", (
        "<p><b>커피와 버스표를 한 번에</b> 사고, <b>회원을 기억해 주는</b> 현금 결제 카페 키오스크입니다.</p>"
        + bullets("기억하는 것: 지난 주문 · 좋아하는 음료 · 평소 옵션 · 자주 가는 노선 · 알레르기 · 이번 주 카페인 · 칭호 · 생일",
                  "카메라로: 얼굴 로그인 · 다가오면 시작 · 자리 비움 확인 · 웃으면 할인",
                  "버스표: 직접 사기(할인) · 인터넷으로 예매한 표 받기(0원) · 저장한 노선으로 바로 사기")
        + flow("대기 화면", "매장 / 포장", "시작 (회원 · 비회원)", "메뉴 · 승차권", "장바구니", "쿠폰 · 포인트 (회원)",
               "현금", "완료")
    )))
    parts.append(section("start", "2. 켜기 · 끄기", (
        steps("<b>1_처음설치</b> 더블클릭 (처음 한 번만 · 인터넷 필요).<br>"
              "“지금 인터넷에서 받을까요? 약 300MB”는 <b>Y</b> (얼굴 인증 모델).",
              "<b>2_시연모드_실행</b> 더블클릭 → 연습용 데이터로 켜져요.<br>저장되지 않고, 끄면 처음 상태로 돌아가요.",
              "끄기: <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Q</kbd> 또는 창 닫기.")
        + '<div class="tip"><b>F2</b> 키를 누르면 왼쪽 아래에 <b>카메라 상태 줄</b>이 나와요.<br>'
          "카메라가 본 거리와 지금 판단(다가오면 시작 · 자리 비움까지 몇 초)을 보여 줘서 시험할 때 좋아요.</div>"
        + "<h3>연습 계정 (비밀번호는 모두 1234)</h3>"
        + "<table><tr><th>계정</th><th>어떤 회원</th></tr>"
          "<tr><td><code>withtop77</code></td><td>김휘원 · 얼음왕 · [얼죽아] · 오늘 생일 · 우유 알레르기 · 저장한 노선 2개 · 카페인 알리미가 곧 넘을 만큼</td></tr>"
          "<tr><td><code>jisung0642</code></td><td>김지성 · 칭호수집가 · 오늘 이미 한 번 옴 · 단골손님 9 / 10</td></tr>"
          "<tr><td><code>bomin</code></td><td>김보민 · MVP보민 · 우유 알레르기 · [디카페인 지킴이] (팀장 · 시연은 안 함)</td></tr>"
          "<tr><td><code>user01</code> ~ <code>user16</code></td><td>주문 습관이 다른 연습 회원 16명</td></tr>"
          "<tr><td>운영자</td><td>시작 화면 오른쪽 위 <b>운영자 메뉴</b> → <code>admin</code> / <code>demo</code></td></tr></table>"
    )))
    parts.append(section("order", "3. 주문해 보기 (처음부터 끝까지)", (
        steps("대기 화면 아무 곳이나 누르기 (카메라가 있으면 1m 안으로 다가와도 돼요).",
              "대기 화면 가운데에 버튼 두 개가 스윽 떠올라요: <b>매장에서 먹어요</b> / <b>포장해 갈게요</b>.<br>완료 화면 · 영수증에 ‘매장’ / ‘포장’으로 남아요. 20초 동안 안 고르면 버튼이 다시 들어가요.",
              "<b>회원 주문</b> 또는 <b>비회원 주문</b>.",
              "메뉴 카드를 눌러 온도 · 사이즈 · 추가 · 수량 → <b>장바구니 담기</b>.",
              "오른쪽 <b>장바구니 확인</b> → <b>결제하기</b>.",
              "회원은 <b>쿠폰 · 포인트</b> 화면을 한 번 더 거쳐요.",
              "현금 버튼으로 돈 넣기 → <b>결제 완료</b>.<br>잔돈이 있으면 회원은 <b>포인트로 적립</b>할 수 있어요.",
              "완료 화면: 대기 번호 · 거스름돈 · 받은 혜택.<br>“더 주문하시겠어요?” 아니요(또는 15초) → 처음으로.")
        + grid(image("00_대기화면", "대기 화면"), image("00B_매장포장", "매장 / 포장 — 가장 먼저 고르기"))
        + grid(image("01_시작화면", "시작 화면 — 회원 / 비회원"), image("03_비회원메뉴", "메뉴 화면"))
        + grid(image("04_옵션선택", "옵션 창"), image("05_장바구니", "장바구니 — 승차권 · 음료가 한 곳에"))
        + grid(image("06_쿠폰포인트", "쿠폰 · 포인트 (회원)"), image("07_현금결제", "현금 결제"))
        + image("08_주문완료", "완료 — 대기 번호 · 포장 · 새 칭호 · 받은 혜택")
        + '<div class="tip">60초 동안 아무것도 안 누르면 45초에 위쪽 띠로 알려 주고, 60초에 처음 화면으로 가요.<br>'
          "카메라가 앞에 사람을 보고 있으면 마지막 터치부터 <b>최대 120초</b>까지 기다려 줘요.<br>"
          "넣은 현금이 있으면 자동으로 돌려줘요.</div>"
    )))
    parts.append(section("login", "4. 회원 로그인", (
        bullets("<b>얼굴 인증</b>: 아이디 입력 → 얼굴 인증 → 50cm 안에서 정면을 보면 돼요.<br>"
                "3번 연속 실패하면 잠기고, 비밀번호로 한 번 로그인하면 풀려요.",
                "<b>비밀번호로 로그인</b>: 로그인하면서 <b>얼굴도 등록할게요</b> · <b>회원카드 신청</b>을 체크할 수 있어요.<br>"
                "이미 얼굴이 있거나 카드가 있는 회원에게는 그 칸이 보이지 않아요.",
                "<b>회원카드</b>: 대기 · 시작 · 로그인 화면에서 카드를 대면 아이디가 채워지고 바로 얼굴 인증으로.",
                "<b>아이디 · 비밀번호 찾기</b>: 아이디는 전화번호로, 비밀번호는 본인 확인 뒤 임시 비밀번호.")
        + grid(image("02_회원로그인", "회원 로그인 — 아이디 + 얼굴"), image("02_비밀번호로그인", "비밀번호 로그인 · 함께 할 일"))
        + "<h3>로그인하면 키오스크가 알아봐요</h3>"
        + bullets("위쪽 띠 인사: “3일 만이에요!” · “어제도 와 주셨네요!” · “오늘 두 번째 방문이에요!”",
                  "이름 앞에 대표 칭호: <b>[얼죽아] 김휘원 님 ›</b> (닉네임보다 이름)",
                  "생일 · 가입 기념 주간이면 축하 팝업과 쿠폰 (해마다 한 번)")
        + grid(image("03_생일팝업", "생일 축하 팝업 · 인사"), image("03_칭호현황", "이름을 누르면 칭호 진행 현황"))
    )))
    parts.append(section("mymenu", "5. My Menu (회원 첫 화면)", (
        bullets("<b>최근 주문 다시 담기 ▶</b>: 지난번 주문을 한 번에 (quick).",
                "<b>★ 저장한 노선</b>: 누르면 그 노선 오늘 시간표로 바로.",
                "<b>♥ 좋아요한 음료</b>: 옵션 창의 ♡로 모아요 (최대 6잔).",
                "<b>카페인 리포트</b>: 이번 주 · 주별 · 월별 그래프.",
                "<b>카페인 알리미</b>: 톱니바퀴로 이번 주 제한(잔 / mg). 넘게 담으려 하면 “그래도 담을까요?”.",
                "<b>옵션 습관</b>: 자주 시키던 메뉴는 평소 옵션(ICE · L · 샷)이 미리 골라져요.",
                "<b>알레르기</b>: 등록한 알레르기 성분이 든 메뉴를 담으면 “알레르기 주의”.")
        + grid(image("03_MyMenu", "My Menu — 다시 담기 · 저장한 노선 · 좋아요"), image("03_카페인경고", "카페인 알리미 질문"))
        + grid(image("03_MyMenu_카페인리포트", "카페인 리포트"), image("03_카페인알리미_설정", "톱니바퀴 → 알리미 설정"))
        + grid(image("04_알레르기경고", "알레르기 주의 (우유)"), image("03_인기탭", "인기 탭 — 좋아요순 · 판매순 · 계절"))
    )))
    parts.append(section("ticket", "6. 버스표 (승차권 탭 · 시뮬레이션)", (
        "<h3>직접 사기</h3>"
        + steps("승차권 → <b>승차권 구매</b> → 도착지 · 날짜 → <b>조회</b>.",
                "시간표에서 버스 → 인원 · 좌석 (고른 좌석은 5분 동안 잡아 둬요).",
                "할인 종류(경로 · 보훈 · 군인 · 장애인 · 중고생 · 초등생) 확인.",
                "<b>장바구니 담고 음료 고르기</b> 또는 <b>바로 결제</b>.<br>음료와 같은 장바구니로 한 번에 결제해요.")
        + "<h3>예매한 표 받기 (예매표 출력)</h3>"
        + steps("승차권 → <b>예매표 출력</b> → 이름 <b>임예찬</b> · 휴대폰 번호 <b>010-2007-2007</b> (또는 예매번호 <b>12345678</b>).",
                "<b>장바구니에 담기 (0원)</b> — 이미 결제한 표라 0원이에요.",
                "음료와 함께(또는 0원으로) 결제를 마치면 출력돼요.")
        + grid(image("T1_승차권탭", "승차권 탭"), image("T1_예매표조회", "예매표 조회 결과"))
        + grid(image("T1_저장노선시간표", "저장한 노선 → 바로 시간표"), image("T1_좌석고르기", "좌석 고르기"))
        + '<div class="tip">쿠폰 · 포인트 할인과 적립은 음료에만 적용돼요. 승차권 할인은 승차권 화면에서 따로 골라요.</div>'
    )))
    parts.append(section("perks", "7. 혜택", (
        "<table><tr><th>혜택</th><th>어떻게</th></tr>"
        "<tr><td>쿠폰 · 포인트</td><td>결제 전 쿠폰 · 포인트 화면에서 골라요 (회원). 방문 5번마다 쿠폰.</td></tr>"
        "<tr><td>잔돈 포인트</td><td>현금 화면에서 거스름돈을 포인트로 적립 (회원).</td></tr>"
        "<tr><td>개인 컵</td><td>장바구니에서 개인 컵(텀블러) 체크 → 음료 1잔마다 에코 포인트.</td></tr>"
        "<tr><td>동전 줄이기 팁</td><td>남은 금액의 천 원 아래를 동전으로 같이 넣으라고 알려 줘요.</td></tr>"
        "<tr><td>미소 미션</td><td>행사 중이면 장바구니에 <b>미소 미션</b> 체크 상자 (개인 컵처럼).<br>"
        "체크하면 작은 카드가 떠요: ‘카메라를 켜는 중이에요 · 잠시만 기다려 주세요’ → 커피잔이 -_- / 웃는 얼굴.<br>"
        "웃은 시간이 <b>모여서 3초</b>가 되면 ‘미소 미션 성공!’ 팝업 (잠깐 멈춰도 0으로 돌아가지 않아요).<br>"
        "카메라 <b>50cm 안</b>에서 · 안 되면 이유가 나와요(정면 · 지금 몇 cm · 입꼬리). 회원은 계정당 한 번.</td></tr>"
        "<tr><td>숨은 쿠폰</td><td>메뉴 화면 왼쪽 위 로고를 1초 안 간격으로 5번 → 100원 쿠폰 (회원마다 한 번).</td></tr>"
        "<tr><td>칭호</td><td>주문이 쌓이면 칭호 7가지. 새 칭호를 받으면 완료 화면에 코랄색 ‘★ 새 칭호 획득!’ 띠.<br>"
        "대기 전광판에 [칭호] 닉네임.</td></tr></table>"
        + "<h3>회원카드</h3>"
        + steps("가입 때 또는 비밀번호 로그인 때 <b>회원카드 신청</b> 체크 → 장바구니에 회원카드 1,000원.",
                "음료와 함께 결제 → 카드는 <b>음료가 나올 때 같이</b> 받아요 (이때는 ‘등록 전’).",
                "My Menu 맨 위 <b>카드 등록</b>을 누르고 카드를 리더기에 대기 (산 바로 그 자리에서도, 다음 주문 때도).<br>"
                "번호가 등록되고 <b>그 주문 10% 할인</b>.",
                "그 뒤로는 매 주문 <b>3% 적립</b> · 주문마다 <b>스탬프 1개</b> (10개면 음료 1잔 무료) · 카드만 대면 로그인.<br>"
                "완료 화면에 쿠폰 모양 스탬프 칸이 나오고, 이번 도장은 코랄색으로 찍혀요.",
                "잃어버리면 <b>My Menu 맨 아래 ‘회원카드를 잃어버렸어요’</b> 또는 카운터(운영자 ‘분실 처리’).<br>"
                "예전 카드는 바로 멈추고, 재발급 카드(500원 · 첫 주문 할인 없음)를 장바구니로 사요.")
        + grid(image("03_카드등록버튼", "My Menu 맨 위 ‘카드 등록’"),
               image("03_회원카드등록", "카드를 대면 — 10% · 3% · 다음부터 카드 로그인"))
        + grid(image("05_미소미션", "미소 미션 — 작은 카드 · 3초 웃기"), image("03_이스터에그", "로고 5번 → 숨은 쿠폰"))
    )))
    parts.append(section("camera", "8. 카메라 기능", (
        bullets("<b>다가오면 시작</b>: 대기 화면에서 1m 안에 1초 서 있으면 매장 / 포장 버튼이 떠올라요.<br>"
                "이미 앞에 앉아 있었다면 <b>한 번 1m 밖으로 물러났다가</b> 다가오면 돼요.",
                "<b>자리 비움 확인</b>: 주문 중 10초 동안 아무도 안 보이면 “자리를 비우셨나요? 로그아웃 (10) · 아니요”.<br>"
                "질문은 사람이 돌아와도 그대로 있어요 (다음 사람이 로그아웃을 누를 수 있게). '아니요'를 누르면 계속.<br>"
                "0초가 되면 넣은 현금을 돌려주고 처음으로.",
                "<b>얼굴 로그인 · 웃으면 할인</b>: 카메라를 쓰는 동안 사람 감지는 잠깐 쉬어요.",
                "<b>F2</b>: 왼쪽 아래 카메라 상태 줄 켜기 / 끄기.")
        + '<div class="tip">영상 · 사진 · 거리 기록은 저장하지 않아요. 얼굴은 특징값(숫자)만 암호화해 저장합니다.<br>'
          "운영자 ‘키오스크 설정’에서 사람 감지를 끄거나 자리 비움 시간을 바꿀 수 있어요.</div>"
    )))
    parts.append(section("demo", "9. 발표 시연 4부분", (
        "<p>팀원 네 명이 한 부분씩 누르고 팀장이 설명해요. 단계별 목차는 <b>시연목차</b> 폴더 (글자만, 크게).</p>"
        "<table><tr><th>순서</th><th>팀원 · 계정</th><th>보여 줄 것</th></tr>"
        "<tr><td>1</td><td>김지성 <code>jisung0642</code></td><td>다가가면 시작 · 그 자리에서 얼굴 등록 → 얼굴 로그인 · 버스표 구매 · 미소 · 잔돈 포인트 · 새 칭호</td></tr>"
        "<tr><td>2</td><td>김휘원 <code>withtop77</code></td><td>비밀번호 로그인 · ‘[얼죽아] 김휘원 님’ · 생일 쿠폰 · 우유 알레르기 · 카페인 알리미 · 다시 담기 · 좋아요 · 저장한 노선 · 숨은 쿠폰</td></tr>"
        "<tr><td>3</td><td>조민기 (그 자리에서 가입 <code>asd1625</code>)</td><td>회원가입 · 얼굴 · 회원카드 구매 → 처음 대서 등록 → 10% · 3% · 스탬프 → 카드로 로그인</td></tr>"
        "<tr><td>4</td><td>임예찬 (비회원)</td><td>예매표 출력 (임예찬 · 010-2007-2007) · 0원 · 커피와 함께 결제</td></tr></table>"
    )))
    parts.append(section("admin", "10. 운영자 화면", (
        "<p>시작 화면 오른쪽 위 <b>운영자 메뉴</b> → 시연 모드는 <code>admin</code> / <code>demo</code>.<br>"
        "운영자 화면은 시간이 지나도 저절로 나가지 않아요. 끝나면 꼭 <b>로그아웃</b>.</p>"
        "<table><tr><th>묶음</th><th>할 수 있는 일</th></tr>"
        "<tr><td>매장</td><td>매출 요약(기간 · 시간대 · 많이 팔린 5개) · 메뉴 · 재고 · 품절</td></tr>"
        "<tr><td>회원</td><td>회원 목록 · 정보 수정 · 주문 기록 · 회원카드(분실 처리 · 등록 해제) · 포인트 조정</td></tr>"
        "<tr><td>혜택 · 행사</td><td>이벤트(적립 · 보너스 · 스마일 할인) · 쿠폰(만들기 · 발급 · 내역) · 혜택 설정</td></tr>"
        "<tr><td>화면 · 설정</td><td>광고 배너 · 키오스크 설정(시간 · 사람 감지 · 승차권 탭)</td></tr>"
        "<tr><td>기록</td><td>운영 기록 걸러 보기</td></tr></table>"
        + grid(image("09_운영자화면", "매출 요약"), image("09_회원카드", "회원카드"))
        + grid(image("09_쿠폰", "쿠폰"), image("09_혜택설정", "혜택 설정"))
    )))
    parts.append(section("real", "11. 실제 모드 (3_실제모드_실행)", (
        bullets("주문 · 회원 · 얼굴 정보를 이 PC의 <b>암호화 금고</b>(<code>program\\data</code>)에 저장해요.",
                "처음 켜면 검은 창에 <b>새 관리자 비밀번호</b>를 물어요. 입력해도 글자가 안 보이는 게 정상이에요.",
                "다음부터는 관리자 아이디 <code>admin</code>과 그 비밀번호로 금고를 열어요.")
        + '<div class="warn"><b>꼭 지켜 주세요</b><br>'
          "관리자 비밀번호 · <code>program\\data</code> 폴더는 다른 사람 · 메신저 · 인터넷에 올리지 마세요.<br>"
          "얼굴 등록은 본인 동의를 받은 사람만 합니다.</div>"
    )))
    parts.append(section("trouble", "12. 문제가 생기면", (
        "<table><tr><th>이럴 때</th><th>이렇게</th></tr>"
        "<tr><td>“Python 을 찾지 못했습니다”</td><td>Python 설치 때 “Add python.exe to PATH” 체크 → 1번 다시.</td></tr>"
        "<tr><td>키오스크가 오류로 멈춤</td><td>검은 창을 찍고 <code>program\\logs\\kiosk_error.log</code>를 팀장에게.</td></tr>"
        "<tr><td>카드를 다시 대도 반응이 없음</td><td>카드를 리더기에서 <b>완전히 떼었다가</b> 다시 대기. "
        "아두이노에 새 스케치(<code>tools\arduino\rfid_rc522_serial</code>)를 올리면 대고 있던 카드도 다시 읽어요.</td></tr>"
        "<tr><td>다가와도 시작이 안 됨</td><td><b>F2</b>로 상태 줄을 켜고 거리 확인 → 한 번 1m 밖으로 물러났다가 다가오기.</td></tr>"
        "<tr><td>얼굴 인증이 안 됨</td><td>밝은 곳 · 정면 · 50cm 안 · 마스크 · 선글라스 벗기. 안 되면 비밀번호.</td></tr>"
        "<tr><td>카메라가 안 잡힘</td><td>다른 카메라 앱을 닫기. <code>program\\tools\\check_camera.py</code>로 확인.</td></tr>"
        "<tr><td>화면이 작음 / 큼</td><td>시작 화면 <b>큰 글자</b> · 전체 화면은 <code>2_시연모드_실행.bat --fullscreen</code>.</td></tr></table>"
    )))
    toc = "".join(f'<li><a href="#{a}">{t}</a></li>' for a, t in (
        ("about", "이 키오스크는"), ("start", "켜기 · 끄기 · 계정"), ("order", "주문해 보기"), ("login", "회원 로그인"),
        ("mymenu", "My Menu"), ("ticket", "버스표"), ("perks", "혜택 · 회원카드"), ("camera", "카메라 기능"),
        ("demo", "시연 4부분"), ("admin", "운영자 화면"), ("real", "실제 모드"), ("trouble", "문제가 생기면")))
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>COFFEE &amp; SPOON 사용 설명서</title>'
            f"<style>{STYLE}</style></head><body><header><h1>COFFEE &amp; SPOON 키오스크 사용 설명서</h1>"
            f"<p>커피와 버스표를 한 번에 · 회원을 기억하는 키오스크 · 팀 공학 한 스푼 · 2026년 11월 3일</p></header><main>"
            f'<nav><b>차례</b><ol>{toc}</ol></nav>{"".join(parts)}</main></body></html>')


# ---------------------------------------------------------------- 시연 테스트 체크리스트
# (묶음, 계정, 해 볼 것, 이렇게 되면 통과)
TESTS = [
    ("시작", "-", "대기 화면을 누르기", "가운데에 매장 / 포장 버튼이 떠오름 (화면은 그대로)"),
    ("시작", "-", "‘포장해 갈게요’ → 비회원 주문 → 음료 1잔 → 결제", "장바구니 제목 ‘주문 합계 · 포장’, 완료 ‘대기 번호 · 포장’, 영수증 ‘· 포장’"),
    ("시작", "-", "시작 화면 아래 언어 · 고대비 · 큰 글자 바꾸기 → 처음으로", "바꾼 것이 다음 손님에게는 기본으로 돌아옴"),
    ("시작", "-", "큰 글자 · 고대비 누르기", "곧바로 바뀜 · 큰 글자는 광고 없이 큰 버튼 · 고대비는 크림색 글자 로고"),
    ("시작", "-", "시작 화면 왼쪽 광고가 넘어가는 것 보기", "메뉴 사진도 잘리지 않고 전체가 보임 · 스마일 배너 아래 ‘이벤트 진행 중’"),
    ("카메라", "-", "F2 → 왼쪽 아래 상태 줄 보기", "‘카메라: 가장 가까운 사람 0.xx m’ 처럼 거리가 바뀜"),
    ("카메라", "-", "대기 화면에서 1m 밖으로 물러났다가 다가와 1초 서 있기", "화면은 그대로 · 가운데에 매장 / 포장 버튼이 스윽 떠오름"),
    ("카메라", "아무 회원", "주문 중 카메라 앞에서 10초 동안 비키기", "‘자리를 비우셨나요? 로그아웃 (10) · 아니요’, 숫자가 줄어듦"),
    ("카메라", "아무 회원", "카메라 앞에 앉은 채 화면을 안 만지고 기다리기", "60초가 지나도 안 나가고, 마지막 터치부터 약 105초에 경고 · 120초에 처음으로"),
    ("카메라", "아무 회원", "위 질문이 뜬 뒤 다시 카메라 앞으로 돌아오기", "질문은 그대로 있음 → ‘아니요’를 누르면 계속 주문"),
    ("카메라", "비회원", "현금 1,000원 넣고 자리 비워 0초까지 기다리기", "처음 화면 · ‘넣은 현금 1,000원을 반환했어요’"),
    ("로그인", "bomin", "비밀번호로 로그인 + ‘얼굴도 등록할게요’ 체크 → 얼굴 등록", "등록 완료 후 메뉴 화면"),
    ("로그인", "bomin", "로그아웃 → 예 → 회원 주문 → bomin → 얼굴 인증", "얼굴로 로그인됨 · ‘[디카페인 지킴이] 김보민 님, 3일 만이에요!’"),
    ("로그인", "-", "없는 아이디 또는 틀린 비밀번호로 로그인", "아이디부터 다시 입력하라는 안내"),
    ("로그인", "user01", "아이디 user01 → 비밀번호로 로그인 화면", "‘회원카드 신청’ 칸이 없음 (이미 카드 있음)"),
    ("로그인", "bomin", "얼굴 등록 뒤 로그아웃 → 예 → bomin → 비밀번호로 로그인 화면", "‘얼굴도 등록할게요’ 칸이 없음"),
    ("로그인", "-", "‘아이디·비밀번호를 잊었어요’ → 전화번호 010-1000-0001로 아이디 찾기", "가려진 아이디 bo*** 가 보임"),
    ("인사 · 칭호", "withtop77", "로그인", "‘[얼죽아] 김휘원 님, 2일 만이에요!’"),
    ("인사 · 칭호", "jisung0642", "로그인", "‘[새내기] 김지성 님, 오늘 두 번째 방문이에요!’"),
    ("인사 · 칭호", "bomin", "위쪽 이름 ‘[디카페인 지킴이] 김보민 님 ›’ 누르기", "칭호 7개 진행 막대"),
    ("인사 · 칭호", "jisung0642", "처음 먹는 음료 1잔 주문 끝내기", "완료 화면 코랄색 띠 ‘★ 새 칭호 획득! [단골손님]’ · 대기자: [단골손님] 칭호수집가"),
    ("인사 · 칭호", "bomin", "메뉴 화면 왼쪽 위 로고를 빠르게 5번", "‘숨은 쿠폰을 찾았어요!’ → 한 번 더 하면 ‘이미 찾으셨네요!’"),
    ("My Menu", "withtop77", "My Menu ‘최근 주문 다시 담기 ▶’", "카페인 알리미 ‘그래도 담을까요?’ → 예 → 2잔이 담김"),
    ("My Menu", "withtop77", "카페인 블록 톱니바퀴 → 잔 / mg · 제한 바꾸기", "블록의 막대 · 남은 양이 바뀜"),
    ("My Menu", "withtop77", "그래프 위 이번 주 · 주별 · 월별 누르기", "그래프가 바뀜"),
    ("My Menu", "withtop77", "커피 → 아메리카노", "옵션 창에 ICE · L · 샷 추가가 미리 골라져 있음"),
    ("My Menu", "아무 회원", "옵션 창 ♡ 좋아요 → My Menu", "좋아요한 음료에 나타남"),
    ("My Menu", "아무 회원", "좋아요를 7번째 음료에 누르기", "‘즐겨찾기는 최대 6잔만 가능해요’ · 하나 풀면 다시 됨"),
    ("알레르기", "bomin", "커피 → 카페라떼 → 담기", "‘알레르기 주의 · 우유’ → 취소 / 그래도 담기"),
    ("버스표", "withtop77", "My Menu ★ 저장한 노선 ‘서울경부 → 대전복합’", "승차권 탭 오늘 시간표로 바로"),
    ("버스표", "jisung0642", "승차권 구매 → 도착지 · 날짜 · 시간 · 인원 · 좌석 → 할인 ‘경로’", "승차권 금액이 할인됨"),
    ("버스표", "jisung0642", "장바구니 담고 음료 고르기 → 음료 담기 → 결제", "장바구니 · 영수증에 승차권과 음료가 같이, 완료 화면에 승차장"),
    ("버스표", "비회원", "예매표 출력 → 임예찬 · 010-2007-2007 → 장바구니에 담기", "장바구니에 예매표 0원 ‘결제하면 출력’"),
    ("버스표", "비회원", "예매표만 담고 결제", "0원 결제 → 완료 화면에 승차권 정보"),
    ("버스표", "-", "예매표 출력 → 예매번호 34567890 조회 (이미 출력한 표)", "‘이미 출력한 표예요’ 안내"),
    ("버스표", "-", "좌석을 고르고 5분 넘게 두기", "장바구니에서 승차권이 빠지고 안내"),
    ("회원카드", "user12", "로그인", "위쪽 띠 ‘받으신 회원카드를 리더기에 대면 등록돼요’ · 회원 줄 ‘카드 등록 전’"),
    ("회원카드", "user12", "My Menu 맨 위 ‘카드 등록’ 누르기", "위쪽 띠 ‘받으신 회원카드를 리더기에 대 주세요 · 20초’"),
    ("회원카드", "user12", "로그인 → My Menu 맨 위 ‘카드 등록’ → 실물 카드를 리더기에 대기", "팝업 하나 ‘회원카드 등록 완료!’ (10% 할인 · 3% 적립) · ‘카드 등록’ 줄이 사라짐"),
    ("회원카드", "user12", "음료를 담고 결제", "쿠폰·포인트 화면 ‘회원카드 첫 주문’ 할인 · 완료 화면 쿠폰 모양 스탬프 칸에 도장 1개"),
    ("회원카드", "user12", "위에서 등록한 카드로: 로그아웃 → 예 → 대기 화면에서 카드 대기", "매장 / 포장 → 아이디가 채워진 로그인"),
    ("회원카드", "-", "등록 안 된 카드를 대기 → 떼었다가 다시 대기", "두 번 다 안내가 다시 반짝이며 뜸 (반응 없음 X)"),
    ("시작", "-", "안내 띠가 뜬 뒤 기다리기 · 안내가 떠 있을 때 처음으로", "천천히 흐려지며 사라짐 · 처음 화면으로 가면 바로 사라짐"),
    ("회원카드", "user01", "My Menu 맨 아래 ‘회원카드를 잃어버렸어요’ → 예", "장바구니에 재발급 카드 500원 · 회원 줄에서 카드 표시가 사라짐"),
    ("회원카드", "아무 회원", "비밀번호 로그인 때 ‘회원카드 신청’ 체크", "장바구니에 회원카드 1,000원 · 결제하면 ‘음료와 함께 받아 가세요’"),
    ("혜택", "jisung0642", "장바구니 ‘미소 미션’ 체크 → 카메라 50cm 안에서 웃기",
     "‘잠시만 기다려 주세요’ → 커피잔 -_- / 웃는 얼굴 · 웃은 시간 x.x / 3초가 쌓임 → ‘미소 미션 성공!’ 팝업 · −500원"),
    ("혜택", "jisung0642", "미소 미션 중 일부러 50cm 밖으로 · 옆을 보기", "‘조금 더 가까이 · 지금 71cm (50cm 안)’ · ‘정면으로 봐 주세요’ 같은 이유가 나옴"),
    ("혜택", "jisung0642", "미소 미션으로 결제한 뒤 ‘예 · 더 주문하기’ → 음료 담고 장바구니", "미소 미션 버튼이 안 보임 (계정당 한 번)"),
    ("혜택", "jisung0642", "현금 넉넉히 넣고 ‘거스름돈을 포인트로’ 체크 → 결제", "완료 화면 잔돈 포인트 +…P"),
    ("혜택", "bomin", "쿠폰 · 포인트 화면에서 쿠폰 고르기 · 포인트 쓰기", "최종 금액이 줄어듦"),
    ("혜택", "아무 회원", "장바구니 ‘개인 컵’ 체크 → 결제", "완료 화면 에코 포인트 +100P"),
    ("혜택", "비회원", "4,500원 음료 → 현금 화면", "‘500원을 동전으로 같이 넣으면 거스름돈에 동전이 없어요’"),
    ("결제", "비회원", "돈을 덜 넣기 → 반환", "부족 금액 안내 · 넣은 돈을 모두 돌려줌"),
    ("결제", "bomin", "포인트로 전액 → 0원 결제", "돈 없이 결제 완료"),
    ("운영자", "admin / demo", "매출 요약 기간 바꾸기", "주문 수 · 매출 · 시간대 그래프가 바뀜"),
    ("운영자", "admin / demo", "메뉴 · 재고: 아메리카노 체크 → 품절로 → 손님 화면", "아메리카노 카드가 품절로"),
    ("운영자", "admin / demo", "회원카드 표 보기", "아이디 · 이름 · 칭호가 따로 된 열"),
    ("운영자", "admin / demo", "회원카드: 사용 중 카드 체크 → 분실 처리", "그 카드는 정지 · 손님 My Menu에 ‘재발급’"),
    ("운영자", "admin / demo", "쿠폰: 회원 체크 → 발급 → 발급 내역", "내역에 ‘미사용’으로"),
    ("운영자", "admin / demo", "혜택 설정: 카드 회원 적립률 5 → 저장 → 가입 화면", "카드 혜택 글에 ‘매 주문 5% 적립’"),
    ("운영자", "admin / demo", "키오스크 설정: 사람 감지 끄기 → 저장", "대기 화면 ‘가까이 오시면…’ 안내가 사라지고 다가와도 시작 안 함"),
]


# 항목마다 이름 (TESTS와 같은 순서). MANUAL은 실물 카메라 · 카드 리더 · 얼굴 · 눈으로 봐야 해서 사람이 직접 하는 것,
# 나머지는 tools/check_checklist.py가 가짜 카메라 · 카드 번호로 직접 해 보고 결과를 checklist_auto.json에 남긴다.
KEYS = [
    "idle_touch", "takeout", "display_reset", "display_feel", "slides_look",
    "f2", "approach", "away_real", "wait120", "away_return", "away_refund",
    "face_enroll", "face_login", "login_fail", "no_card_option", "no_face_option", "find_id",
    "greet_withtop", "greet_jisung", "title_sheet", "new_title", "easter_egg",
    "quick", "caffeine_gear", "caffeine_views", "habit", "like", "like_max", "allergy",
    "saved_route", "ticket_discount", "ticket_drink", "reservation_cart", "reservation_pay", "reservation_printed",
    "seat_hold", "card_login_notice", "card_button", "card_tap", "card_pay", "idle_card", "unknown_retap",
    "notice_fade", "lost_card", "card_apply", "smile_real", "smile_hints", "smile_once", "change_points",
    "coupon_points", "eco", "coin_tip", "short_refund", "zero_won",
    "admin_sales", "admin_sold_out", "admin_card_columns", "admin_lost", "admin_coupon", "admin_perks",
    "admin_presence_off",
]
MANUAL = {"card_tap", "idle_card", "unknown_retap"}      # 11/04: 사람이 볼 것은 실물 카드 리더만 남긴다
# 사람이 봐야 하지만 11/04 요청으로 체크리스트에서 뺀 것 (실물 카메라 · 얼굴 · 화면 느낌). 자동 확인도 하지 않는다.
LEFT_OUT = {"display_feel", "slides_look", "f2", "approach", "away_real", "wait120", "away_return",
            "face_enroll", "face_login", "smile_real", "smile_hints"}
assert len(KEYS) == len(TESTS), (len(KEYS), len(TESTS))

def auto_section():
    """tools/check_checklist.py가 직접 해 본 결과 (가짜 카메라 · 카드 번호). 없으면 빈 글."""
    path = DOCS / "checklist_auto.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    results = data["results"]
    passed = sum(r["ok"] for r in results.values())
    rows = []
    for key, (group, account, todo, expect) in zip(KEYS, TESTS):
        if key not in results:
            continue
        r = results[key]
        mark = '<b style="color:var(--ok)">통과</b>' if r["ok"] else '<b style="color:var(--bad)">문제</b>'
        rows.append(f"<tr><td>{mark}</td><td>{group}</td><td><code>{account}</code></td><td>{todo}</td>"
                    f"<td>{html.escape(r['detail'])}</td></tr>")
    when = data["at"].replace("T", " ")
    return (f'<section><details><summary><b>자동으로 확인한 것 {len(results)}개 · 통과 {passed}</b> '
            f'<span style="color:var(--text2)">({when} · 가짜 카메라 · 카드 번호로 직접 해 봄)</span></summary>'
            '<table><tr><th>결과</th><th>묶음</th><th>계정</th><th>해 본 것</th><th>확인한 내용</th></tr>'
            + "".join(rows) + "</table></details></section>")


def checklist():
    manual = [(group, account, todo, expect) for key, (group, account, todo, expect) in zip(KEYS, TESTS)
              if key in MANUAL]
    rows = json.dumps([{"group": g, "account": a, "todo": t, "expect": e} for g, a, t, e in manual], ensure_ascii=False)
    groups = json.dumps(list(dict.fromkeys(g for g, *_ in manual)), ensure_ascii=False)
    script = """
const TESTS = __ROWS__;
const GROUPS = __GROUPS__;
const KEY = "coffee-spoon-test-1104-card";
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { state = {}; }
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
let filter = "전체";
function render() {
  const chips = document.getElementById("chips");
  chips.innerHTML = "";
  ["전체", ...GROUPS].forEach(g => {
    const b = document.createElement("button");
    b.textContent = g; b.className = "chip" + (g === filter ? " on" : "");
    b.onclick = () => { filter = g; render(); };
    chips.appendChild(b);
  });
  const list = document.getElementById("list");
  list.innerHTML = "";
  TESTS.forEach((t, i) => {
    if (filter !== "전체" && t.group !== filter) return;
    const s = state[i] || {};
    const row = document.createElement("div");
    row.className = "item " + (s.result || "");
    row.innerHTML = `<div class="head"><span class="no">${i + 1}</span><span class="tag">${t.group}</span>`
      + `<span class="acct">${t.account}</span></div>`
      + `<div class="todo">${t.todo}</div><div class="expect">→ ${t.expect}</div>`
      + `<div class="btns"><button data-r="pass">통과</button><button data-r="fail">문제</button>`
      + `<input placeholder="문제였다면 어떻게 됐는지 메모" value="${(s.note || "").replace(/"/g, "&quot;")}"></div>`;
    row.querySelectorAll("button").forEach(b => {
      if (s.result === b.dataset.r) b.classList.add("on");
      b.onclick = () => { state[i] = {...s, result: s.result === b.dataset.r ? "" : b.dataset.r}; save(); render(); };
    });
    row.querySelector("input").onchange = e => { state[i] = {...(state[i] || {}), note: e.target.value}; save(); };
    list.appendChild(row);
  });
  const pass = Object.values(state).filter(s => s.result === "pass").length;
  const fail = Object.values(state).filter(s => s.result === "fail").length;
  document.getElementById("summary").textContent = `통과 ${pass} · 문제 ${fail} · 남음 ${TESTS.length - pass - fail} / 전체 ${TESTS.length}`;
}
function copyProblems() {
  const lines = TESTS.map((t, i) => [t, state[i] || {}, i]).filter(([, s]) => s.result === "fail")
    .map(([t, s, i]) => `${i + 1}. [${t.group}] ${t.todo} → 기대: ${t.expect}${s.note ? " / 실제: " + s.note : ""}`);
  const text = lines.length ? "시연 테스트 문제 목록\\n" + lines.join("\\n") : "문제로 표시한 항목이 없어요";
  const box = document.getElementById("copybox");
  box.value = text; box.style.display = "block"; box.select();
  try { navigator.clipboard.writeText(text); } catch (e) {}
}
function resetAll() { if (confirm("체크를 모두 지울까요?")) { state = {}; save(); render(); } }
render();
""".replace("__ROWS__", rows).replace("__GROUPS__", groups)
    extra = """
.top { display:flex; flex-wrap:wrap; gap:10px; align-items:center; justify-content:space-between; }
#summary { font-weight:700; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin:12px 0 4px; }
.chip, .btns button, .act { border:1px solid var(--line); background:var(--card); color:var(--brown); border-radius:999px;
  padding:6px 14px; font:inherit; font-size:15px; cursor:pointer; }
.chip.on { background:var(--caramel); color:#fff; border-color:var(--caramel); }
.item { border:1px solid var(--line); border-radius:14px; padding:12px 16px; margin:10px 0; background:var(--card); }
.item.pass { background:var(--okbg); } .item.fail { background:var(--badbg); }
.head { display:flex; gap:8px; align-items:center; font-size:14px; color:var(--text2); }
.no { font-weight:700; color:var(--caramel); } .tag { background:var(--cream); border-radius:6px; padding:0 8px; }
.acct { font-family:Consolas,monospace; }
.todo { font-weight:700; margin-top:4px; } .expect { color:var(--text2); }
.btns { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; align-items:center; }
.btns button[data-r="pass"].on { background:var(--ok); color:#fff; border-color:var(--ok); }
.btns button[data-r="fail"].on { background:var(--bad); color:#fff; border-color:var(--bad); }
.btns input { flex:1; min-width:200px; border:1px solid var(--line); border-radius:10px; padding:6px 10px; font:inherit;
  font-size:15px; background:var(--card); color:var(--brown); }
#copybox { display:none; width:100%; height:140px; margin-top:10px; font:14px/1.5 Consolas,monospace; }
"""
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>시연 테스트 체크리스트</title>'
            f"<style>{STYLE}{extra}</style></head><body><header><h1>시연 테스트 체크리스트</h1>"
            f"<p>실물 카메라 · 카드 리더 · 얼굴 · 눈으로 봐야 하는 것만 남겼어요 · 나머지는 자동으로 확인했어요</p></header><main>"
            f'<section><div class="top"><span id="summary"></span><span>'
            f'<button class="act" onclick="copyProblems()">문제 목록 복사</button> '
            f'<button class="act" onclick="resetAll()">처음부터</button></span></div>'
            f'<div class="chips" id="chips"></div><textarea id="copybox" readonly></textarea>'
            f'<p class="tip">‘문제’를 누르고 메모를 남긴 뒤 <b>문제 목록 복사</b>를 누르면, 그대로 붙여 넣어 보낼 수 있어요.<br>'
            f"카메라 항목은 키오스크에서 <b>F2</b>를 눌러 왼쪽 아래 상태 줄을 켜고 해 보세요. "
            f"체크는 이 브라우저에만 저장돼요.</p></section>"
            f'<section><h2>직접 해 볼 것 ({len(manual)}개)</h2><div id="list"></div></section>{auto_section()}'
            f'</main><script>{script}</script></body></html>')


def main():
    (DOCS / "사용설명서.html").write_text(manual(), encoding="utf-8")
    (DOCS / "시연_테스트_체크리스트.html").write_text(checklist(), encoding="utf-8")
    print("사용설명서.html · 시연_테스트_체크리스트.html 을 만들었습니다")


if __name__ == "__main__":
    main()
