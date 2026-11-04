"""키오스크 옆에 붙일 QR 안내지를 만든다 (11/04 회의).

사용: python tools/make_qr.py [저장할 폴더]      → QR_회원페이지.png · QR_안내지.html
QR에는 이 PC의 와이파이 주소(예: http://192.168.0.12:8080/)가 들어간다. 발표 장소의 와이파이에 연결한 뒤
그 자리에서 다시 만들어야 한다 (장소마다 주소가 다르다). 키오스크는 --web 으로 켜야 페이지가 열린다.
QR 그림은 segno가 그린다 (pip install segno).
"""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gui.member_site import PORT, local_ip


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        import segno
    except ImportError:
        raise SystemExit("QR을 그리려면 segno가 필요해요:  .venv\\Scripts\\python -m pip install segno")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "release"
    out.mkdir(parents=True, exist_ok=True)
    url = f"http://{local_ip()}:{PORT}/"
    png = out / "QR_회원페이지.png"
    segno.make(url, error="m").save(str(png), scale=12, border=2, dark="#3C1B03")
    logo = ROOT / "gui" / "assets" / "logo_main.png"
    logo_tag = (f'<img class="logo" src="data:image/png;base64,{base64.b64encode(logo.read_bytes()).decode()}">'
                if logo.exists() else "")
    qr = base64.b64encode(png.read_bytes()).decode()
    (out / "QR_안내지.html").write_text(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>QR 안내지</title><style>
body {{ margin:0; background:#F7EEE3; font-family:"Noto Sans KR","Malgun Gothic",sans-serif; color:#3C1B03; }}
.sign {{ width:420px; margin:30px auto; background:#fff; border-radius:28px; padding:30px 30px 24px; text-align:center;
        box-shadow:0 6px 24px rgba(60,27,3,.12); }}
.logo {{ width:110px; }} h1 {{ font-size:28px; margin:8px 0 4px; }} p {{ margin:4px 0; color:#7A6252; font-size:17px; }}
.qr {{ width:300px; margin:16px 0 8px; }} .url {{ font-size:14px; color:#B66B2E; }}
@media print {{ body {{ background:#fff; }} .sign {{ box-shadow:none; }} }}
</style></head><body><div class="sign">{logo_tag}<h1>휴대폰으로 회원가입</h1>
<p>QR을 찍으면 가입 · 내 정보 고치기를 할 수 있어요</p><p>주문은 키오스크에서 해 주세요</p>
<img class="qr" src="data:image/png;base64,{qr}"><div class="url">{url}</div></div></body></html>""",
                                       encoding="utf-8")
    print(f"QR 주소: {url}")
    print(f"만들었어요: {png}  ·  {out / 'QR_안내지.html'}")
    if url.startswith("http://127."):
        print("※ 와이파이에 연결되어 있지 않아 이 PC 안에서만 열리는 주소예요. 와이파이에 연결하고 다시 만들어 주세요.")


if __name__ == "__main__":
    main()
