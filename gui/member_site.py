"""QR 회원 페이지 (11/04 회의): 키오스크 옆에 붙인 QR을 휴대폰으로 찍으면 열리는 작은 웹 페이지.

회원가입 · 로그인 · 내 정보 보기 · 고치기(닉네임 · 전화번호 · 생일 · 알레르기 · 마케팅 동의 · 비밀번호)만 한다.
주문 기능은 없다. 키오스크 프로그램 안에서 뒤 스레드로 돌고 키오스크와 같은 금고(회원 데이터)를 쓴다.
그래서 휴대폰으로 가입하면 바로 키오스크에서 그 아이디로 로그인할 수 있다.

추가 설치 없이 파이썬 기본 http.server로 만든다 (Flask 대신). 같은 와이파이에 있는 휴대폰에서
http://(이 PC 주소):8080 으로 들어온다. QR 그림은 tools/make_qr.py가 만든다.
시연용이라 https가 아니다. 실제 매장이라면 https와 로그인 횟수 제한을 더해야 한다.
"""
import html
import secrets
import socket
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from core.validators import normalize_phone
from domain.allergens import ALLERGENS
from domain.benefits import coupons_of
from domain.customers import (login_with_password, register_customer, update_member_info, validate_password_pair,
                              verify_member_password, hash_member_password)
from domain.titles import title_name

PORT = 8080
SESSION_SECONDS = 30 * 60
LOGO = Path(__file__).parent / "assets" / "logo_main.png"
LOCK = threading.Lock()          # 키오스크 화면과 동시에 금고를 고치지 않게 웹 쪽 작업은 하나씩

STYLE = """
:root { --bg:#F7EEE3; --card:#FFFFFF; --brown:#3C1B03; --caramel:#B66B2E; --light:#F1DFCB; --line:#E6D6C4;
        --text2:#7A6252; --error:#B4236B; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--brown); font-family:"Noto Sans KR","Malgun Gothic",sans-serif;
       font-size:17px; line-height:1.55; }
main { max-width:460px; margin:0 auto; padding:20px 16px 48px; }
header { text-align:center; padding:8px 0 4px; }
header img { width:170px; }
h1 { font-size:24px; margin:6px 0 2px; }
.sub { color:var(--text2); font-size:15px; margin:0 0 14px; text-align:center; }
.card { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px; margin:14px 0; }
label { display:block; font-weight:700; font-size:15px; margin:12px 0 4px; }
input[type=text], input[type=password], input[type=tel], input[type=date] {
  width:100%; padding:12px 14px; border:1.5px solid var(--line); border-radius:12px; font-size:17px; background:#fff; }
input:focus { outline:none; border-color:var(--caramel); }
/* 11/04: 아이폰은 날짜 칸이 자기 모양을 고집해 옆으로 튀어나온다 → 기본 모양을 끄고 다른 칸과 같은 폭 · 왼쪽 정렬 */
input[type=date] { -webkit-appearance:none; appearance:none; display:block; min-width:0; max-width:100%;
                   min-height:50px; text-align:left; }
input[type=date]::-webkit-date-and-time-value { text-align:left; }
.btn { display:block; width:100%; text-align:center; padding:14px; border-radius:14px; font-size:18px; font-weight:700;
       text-decoration:none; border:none; cursor:pointer; margin-top:14px; }
.primary { background:var(--brown); color:#fff; }
.outline { background:#fff; color:var(--brown); border:1.5px solid var(--line); }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }
.chips label { display:inline-flex; align-items:center; gap:6px; margin:0; font-weight:400; background:var(--bg);
               border-radius:999px; padding:6px 12px; font-size:15px; }
.check { display:flex; gap:8px; align-items:flex-start; font-weight:400; }
.error { color:var(--error); font-weight:700; font-size:18px; margin:8px 0; }
.ok { background:var(--light); border-radius:12px; padding:10px 14px; font-weight:700; }
.info { display:grid; grid-template-columns:auto 1fr; gap:6px 14px; font-size:16px; }
.info b { color:var(--text2); font-weight:400; }
.note { color:var(--text2); font-size:14px; }
"""


def page(title, body):
    logo = '<img src="/logo.png" alt="COFFEE & SPOON">' if LOGO.exists() else ""
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)} · COFFEE &amp; SPOON</title><style>{STYLE}</style></head><body><main>"
            f"<header>{logo}<h1>{html.escape(title)}</h1></header>{body}</main></body></html>")


def field(name, label_text, value="", kind="text", hint=""):
    extra = ' inputmode="numeric"' if kind == "tel" else ""
    hint = f'<div class="note">{hint}</div>' if hint else ""
    return (f'<label for="{name}">{label_text}</label><input id="{name}" name="{name}" type="{kind}"'
            f' value="{html.escape(value)}"{extra}>{hint}')


def allergy_chips(chosen):
    boxes = "".join(f'<label><input type="checkbox" name="allergies" value="{html.escape(a)}"'
                    f'{" checked" if a in chosen else ""}>{html.escape(a)}</label>' for a in ALLERGENS)
    return f'<label>알레르기 (있으면 골라 주세요)</label><div class="chips">{boxes}</div>'


class MemberSite:
    """웹 페이지 서버. start()하면 뒤 스레드에서 돈다."""

    def __init__(self, vault_getter, port=PORT):
        self.vault_getter = vault_getter       # () -> 지금 키오스크 금고 (잠금 해제 전이면 None)
        self.port = port
        self.sessions = {}                     # 쿠키 값 -> (회원 번호, 만료 시각)
        self.server = None

    @property
    def url(self):
        return f"http://{local_ip()}:{self.port}/"

    def start(self):
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):       # 콘솔을 어지럽히지 않는다
                pass

            def do_GET(self):
                site.handle(self, "GET")

            def do_POST(self):
                site.handle(self, "POST")

        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self.port = self.server.server_address[1]          # 0을 주면 빈 포트 (테스트)
        threading.Thread(target=self.server.serve_forever, name="member-site", daemon=True).start()
        return self.url

    def stop(self):
        if self.server is not None:
            self.server.shutdown()

    # ---- 요청 처리
    def handle(self, request, method):
        path = request.path.split("?")[0]
        form = {}
        if method == "POST":
            length = int(request.headers.get("Content-Length") or 0)
            form = parse_qs(request.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        vault = self.vault_getter()
        if path == "/logo.png" and LOGO.exists():
            return self.send(request, 200, LOGO.read_bytes(), "image/png")
        if vault is None:
            return self.send_page(request, "잠시 후 다시", '<div class="card">키오스크가 아직 준비 중이에요.</div>')
        customer_id = self.current(request)
        routes = {"/": self.home, "/login": self.login, "/signup": self.signup, "/me": self.me,
                  "/password": self.password, "/logout": self.logout}
        handler = routes.get(path)
        if handler is None:
            return self.send_page(request, "없는 페이지", '<div class="card"><a class="btn outline" href="/">처음으로</a></div>', 404)
        with LOCK:
            return handler(request, method, form, vault, customer_id)

    def current(self, request):
        cookie = SimpleCookie(request.headers.get("Cookie", ""))
        token = cookie["cs_member"].value if "cs_member" in cookie else ""
        entry = self.sessions.get(token)
        if entry is None or entry[1] < time.time():
            self.sessions.pop(token, None)
            return None
        self.sessions[token] = (entry[0], time.time() + SESSION_SECONDS)
        return entry[0]

    def sign_in(self, request, customer_id, location="/me"):
        token = secrets.token_urlsafe(24)
        self.sessions[token] = (customer_id, time.time() + SESSION_SECONDS)
        request.send_response(303)
        request.send_header("Set-Cookie", f"cs_member={token}; Path=/; HttpOnly; SameSite=Strict")
        request.send_header("Location", location)
        request.end_headers()

    @staticmethod
    def redirect(request, location):
        request.send_response(303)
        request.send_header("Location", location)
        request.end_headers()

    @staticmethod
    def send(request, status, data, kind):
        request.send_response(status)
        request.send_header("Content-Type", kind)
        request.send_header("Content-Length", str(len(data)))
        request.send_header("Cache-Control", "no-store")
        request.end_headers()
        request.wfile.write(data)

    def send_page(self, request, title, body, status=200):
        self.send(request, status, page(title, body).encode("utf-8"), "text/html; charset=utf-8")

    # ---- 페이지
    def home(self, request, method, form, vault, customer_id):
        if customer_id:
            return self.redirect(request, "/me")
        body = ('<p class="sub">COFFEE &amp; SPOON 회원 페이지<br>가입 · 내 정보 고치기를 휴대폰에서 할 수 있어요<br>'
                '(주문은 키오스크에서)</p><div class="card">'
                '<a class="btn primary" href="/login">로그인</a><a class="btn outline" href="/signup">회원가입</a></div>')
        self.send_page(request, "회원 페이지", body)

    def login(self, request, method, form, vault, customer_id):
        error, login_id = "", ""
        if method == "POST":
            login_id = form.get("login_id", [""])[0]
            try:
                customer = login_with_password(vault, login_id, form.get("password", [""])[0])
                return self.sign_in(request, customer["id"])
            except ValueError as problem:
                error = str(problem)
        body = (f'<div class="card"><form method="post">{field("login_id", "아이디", login_id)}'
                f'{field("password", "비밀번호", kind="password")}'
                + (f'<div class="error">{html.escape(error)}</div>' if error else "")
                + '<button class="btn primary">로그인</button></form>'
                '<a class="btn outline" href="/signup">처음이에요 · 회원가입</a></div>')
        self.send_page(request, "로그인", body)

    def signup(self, request, method, form, vault, customer_id):
        get = lambda key: form.get(key, [""])[0]
        error = ""
        if method == "POST":
            try:
                validate_password_pair(get("password"), get("confirm"))
                record = register_customer(
                    vault, get("name"), get("nickname"), get("phone"), get("login_id"), get("password"),
                    birthday=get("birthday"), allergies=form.get("allergies", []),
                    privacy_agreed=bool(get("privacy")), marketing_agreed=bool(get("marketing")))
                return self.sign_in(request, record["id"], "/me?new=1")
            except ValueError as problem:
                error = str(problem)
        body = ('<div class="card"><form method="post">'
                + field("name", "이름 *", get("name")) + field("login_id", "아이디 * (영문 · 숫자)", get("login_id"))
                + field("password", "비밀번호 * (4자 이상)", kind="password") + field("confirm", "비밀번호 다시 *", kind="password")
                + field("phone", "전화번호 *", get("phone"), "tel", "숫자만 넣어도 돼요")
                + field("nickname", "닉네임 (안 넣으면 이름)", get("nickname"))
                + field("birthday", "생일 (넣으면 생일 쿠폰)", get("birthday"), "date")
                + allergy_chips(form.get("allergies", []))
                + '<label class="check"><input type="checkbox" name="privacy" value="1"> [필수] 개인정보 수집 · 이용 동의</label>'
                + '<label class="check"><input type="checkbox" name="marketing" value="1"> [선택] 이벤트 · 혜택 알림 동의</label>'
                + (f'<div class="error">{html.escape(error)}</div>' if error else "")
                + '<button class="btn primary">가입하기</button></form>'
                '<p class="note">얼굴 로그인과 회원카드는 키오스크에서 신청할 수 있어요.</p></div>')
        self.send_page(request, "회원가입", body)

    def me(self, request, method, form, vault, customer_id):
        if not customer_id:
            return self.redirect(request, "/login")
        customers = vault.read("customers", default={})
        customer = customers.get(customer_id)
        if customer is None:
            return self.logout(request, method, form, vault, customer_id)
        extra = customer["extra"]
        get = lambda key, default="": form.get(key, [default])[0]
        message, error = "", ""
        if "new=1" in request.path:
            message = "가입했어요! 키오스크에서 이 아이디로 로그인하면 돼요"
        if method == "POST":
            try:
                customer = update_member_info(vault, customer_id, get("nickname"), get("phone"), get("birthday"),
                                              form.get("allergies", []), marketing_agreed=bool(get("marketing")))
                extra = customer["extra"]
                message = "저장했어요"
            except ValueError as problem:
                error = str(problem)
        title = f"[{title_name(extra['title'])}] " if extra.get("title") else ""
        name = f"{title}{customer['name']}"
        info = (f'<div class="info"><b>이름</b><span>{html.escape(name)} 님</span>'
                f'<b>아이디</b><span>{html.escape(extra["login_id"])}</span>'
                f'<b>포인트</b><span>{extra.get("points", 0):,}P</span>'
                f'<b>쿠폰</b><span>{len(coupons_of(customer))}장</span>'
                f'<b>방문</b><span>{extra.get("visits", 0)}회</span>'
                f'<b>얼굴 로그인</b><span>{"등록됨" if extra.get("face_enrolled") else "키오스크에서 등록"}</span></div>')
        body = (f'<div class="card">{info}</div>'
                + (f'<div class="ok">{html.escape(message)}</div>' if message else "")
                + (f'<div class="error">{html.escape(error)}</div>' if error else "")
                + '<div class="card"><form method="post"><b>내 정보 고치기</b>'
                + field("nickname", "닉네임", get("nickname", extra.get("nickname", "")))
                + field("phone", "전화번호", get("phone", customer.get("phone", "")), "tel")
                + field("birthday", "생일", get("birthday", extra.get("birthday", "")), "date")
                + allergy_chips(form.get("allergies", extra.get("allergies", [])))
                + f'<label class="check"><input type="checkbox" name="marketing" value="1"'
                  f'{" checked" if extra.get("marketing_agreed") else ""}> 이벤트 · 혜택 알림 받기</label>'
                + '<button class="btn primary">저장</button></form></div>'
                '<div class="card"><form method="post" action="/password"><b>비밀번호 바꾸기</b>'
                + field("current", "지금 비밀번호", kind="password") + field("password", "새 비밀번호", kind="password")
                + field("confirm", "새 비밀번호 다시", kind="password")
                + '<button class="btn outline">비밀번호 바꾸기</button></form></div>'
                '<a class="btn outline" href="/logout">로그아웃</a>'
                '<p class="note">주문은 키오스크에서 해 주세요. 이 페이지에는 주문 기능이 없어요.</p>')
        self.send_page(request, "내 정보", body)

    def password(self, request, method, form, vault, customer_id):
        if not customer_id or method != "POST":
            return self.redirect(request, "/me")
        get = lambda key: form.get(key, [""])[0]
        customers = vault.read("customers", default={})
        customer = customers.get(customer_id)
        try:
            if customer is None or not verify_member_password(get("current"), customer["extra"]["password_hash"]):
                raise ValueError("지금 비밀번호가 맞지 않아요")
            validate_password_pair(get("password"), get("confirm"))
            customer["extra"]["password_hash"] = hash_member_password(get("password"))
            customer["extra"].pop("must_change_password", None)
            vault.write("customers", customers)
            text = '<div class="ok">비밀번호를 바꿨어요</div>'
        except ValueError as problem:
            text = f'<div class="error">{html.escape(str(problem))}</div>'
        self.send_page(request, "비밀번호", f'{text}<a class="btn primary" href="/me">내 정보로</a>')

    def logout(self, request, method, form, vault, customer_id):
        cookie = SimpleCookie(request.headers.get("Cookie", ""))
        if "cs_member" in cookie:
            self.sessions.pop(cookie["cs_member"].value, None)
        self.redirect(request, "/")


def local_ip():
    """같은 와이파이의 휴대폰이 들어올 이 PC 주소 (예: 192.168.0.12). 못 찾으면 127.0.0.1."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))            # 실제로 보내지는 않는다 (나가는 길만 고른다)
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def start_member_site(vault_getter, port=PORT):
    """키오스크 창에서 부른다. 포트를 못 열면 None (키오스크는 그대로 돈다)."""
    site = MemberSite(vault_getter, port)
    try:
        site.start()
    except OSError:
        return None
    return site
