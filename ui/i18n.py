"""손님 화면 다국어 문구. 한국어·English·日本語·中文.

- 손님이 보는 화면(HOME·로그인·가입·메뉴·옵션·혜택·결제·영수증)만 번역한다.
- 운영자 화면과 계산 모듈(domain/)의 오류 문구는 한국어로 둔다.
- 메뉴 이름은 한국어/영어만 준비했다. 일본어·중국어 화면에서는 영어 이름을 쓴다.
- 문구를 추가할 때는 네 언어를 모두 채운다. 빠지면 한국어로 표시된다.
"""

LANGUAGES = {"ko": "한국어", "en": "English", "ja": "日本語", "zh": "中文"}
DEFAULT_LANGUAGE = "ko"

TEXT = {
    # 공통 접근성 바
    "lang": {"ko": "언어", "en": "Language", "ja": "言語", "zh": "语言"},
    "high_contrast": {"ko": "고대비", "en": "High contrast", "ja": "ハイコントラスト", "zh": "高对比度"},
    "large_mode": {"ko": "큰 글자", "en": "Large text", "ja": "大きな文字", "zh": "大字体"},
    # 01 HOME
    "home_title": {"ko": "어떤 방식으로 주문하시겠어요?", "en": "How would you like to order?",
                   "ja": "ご注文方法をお選びください", "zh": "请选择点单方式"},
    "home_desc": {"ko": "회원은 나만의 혜택으로, 비회원은 간편하게 주문하세요. 회원은 ID와 얼굴로 로그인하고, 얼굴이 실패하면 비밀번호를 사용합니다.",
                  "en": "Members get their own benefits; guests can order right away. Members sign in with ID + face, or a password if the face check fails.",
                  "ja": "会員は特典付きで、非会員はそのまま簡単にご注文いただけます。会員はIDと顔でログインし、顔認証に失敗した場合はパスワードを使います。",
                  "zh": "会员可享受专属优惠，非会员可直接点单。会员使用ID+人脸登录，人脸识别失败时可使用密码。"},
    "member_order": {"ko": "회원 주문", "en": "Member order", "ja": "会員注文", "zh": "会员点单"},
    "guest_order": {"ko": "비회원 주문", "en": "Guest order", "ja": "非会員注文", "zh": "非会员点单"},
    "signup": {"ko": "회원 가입", "en": "Sign up", "ja": "会員登録", "zh": "注册会员"},
    "operator": {"ko": "운영자 메뉴", "en": "Staff menu", "ja": "スタッフメニュー", "zh": "管理员菜单"},
    # 02 회원 로그인
    "member_login": {"ko": "회원 로그인", "en": "Member sign-in", "ja": "会員ログイン", "zh": "会员登录"},
    "demo_hint": {"ko": "시연 계정 예시: bomin / 비밀번호 1234", "en": "Demo account: bomin / password 1234",
                  "ja": "デモアカウント: bomin / パスワード 1234", "zh": "演示账号: bomin / 密码 1234"},
    "ph_member_id": {"ko": "회원 ID (예: bomin)", "en": "Member ID (e.g. bomin)", "ja": "会員ID (例: bomin)", "zh": "会员ID (例: bomin)"},
    "ph_member_pw": {"ko": "비밀번호 (얼굴 실패 시 사용)", "en": "Password (if face check fails)",
                     "ja": "パスワード (顔認証失敗時)", "zh": "密码 (人脸识别失败时使用)"},
    "face_login": {"ko": "ID + 얼굴 로그인", "en": "ID + face sign-in", "ja": "ID + 顔でログイン", "zh": "ID + 人脸登录"},
    "pw_login": {"ko": "ID + 비밀번호 로그인", "en": "ID + password sign-in", "ja": "ID + パスワードでログイン", "zh": "ID + 密码登录"},
    "face_enroll": {"ko": "비밀번호 확인 후 얼굴 등록", "en": "Verify password & register face",
                    "ja": "パスワード確認後に顔を登録", "zh": "验证密码后注册人脸"},
    "as_guest": {"ko": "비회원으로 계속", "en": "Continue as guest", "ja": "非会員で続ける", "zh": "以非会员继续"},
    "to_home": {"ko": "처음으로", "en": "Start over", "ja": "最初に戻る", "zh": "返回首页"},
    # 회원 가입
    "signup_title": {"ko": "회원 데이터 카드 만들기", "en": "Create your member card", "ja": "会員カードを作成", "zh": "创建会员卡"},
    "ph_name": {"ko": "예: 홍길동", "en": "e.g. Jamie Kim", "ja": "例: 山田花子", "zh": "例: 王小明"},
    "ph_nickname": {"ko": "닉네임 (대기자 명단에 표시)", "en": "Nickname (shown on the waiting list)",
                    "ja": "ニックネーム (呼び出し時に表示)", "zh": "昵称 (显示在取餐名单)"},
    "ph_phone": {"ko": "전화번호 (숫자만 입력해도 010-xxxx-xxxx로 바뀝니다)", "en": "Phone (digits become 010-xxxx-xxxx)",
                 "ja": "電話番号 (数字のみで 010-xxxx-xxxx に変換)", "zh": "电话号码 (仅输入数字会转换为 010-xxxx-xxxx)"},
    "ph_login_id": {"ko": "영문 소문자·숫자·_ 4~20자", "en": "a-z, 0-9, _ · 4-20 chars",
                    "ja": "英小文字・数字・_ 4〜20文字", "zh": "小写字母·数字·_ 4~20位"},
    "ph_password": {"ko": "비밀번호 (4자 이상)", "en": "Password (4+ chars)", "ja": "パスワード (4文字以上)", "zh": "密码 (至少4位)"},
    "ph_birthday": {"ko": "생일 (선택, 예: 06-08)", "en": "Birthday (optional, e.g. 06-08)",
                    "ja": "誕生日 (任意、例: 06-08)", "zh": "生日 (可选, 例: 06-08)"},
    "ph_allergies": {"ko": "알레르기 (선택, 쉼표로 구분: 우유, 견과류)", "en": "Allergies (optional, comma separated: 우유, 견과류)",
                     "ja": "アレルギー (任意、カンマ区切り: 우유, 견과류)", "zh": "过敏原 (可选, 用逗号分隔: 우유, 견과류)"},
    "privacy": {"ko": "개인정보 활용 동의 (필수)", "en": "I agree to personal data use (required)",
                "ja": "個人情報の利用に同意 (必須)", "zh": "同意使用个人信息 (必选)"},
    "marketing": {"ko": "마케팅 수신 동의 (선택)", "en": "Receive marketing messages (optional)",
                  "ja": "マーケティング受信に同意 (任意)", "zh": "同意接收营销信息 (可选)"},
    "face_consent": {"ko": "얼굴 특징 정보 수집·이용에 동의합니다 (원본 사진은 저장하지 않음)",
                     "en": "I agree to the collection and use of face features (no photos stored)",
                     "ja": "顔特徴情報の収集・利用に同意します (写真は保存しません)",
                     "zh": "同意收集和使用人脸特征信息 (不保存照片)"},
    "create_card": {"ko": "카드 만들기", "en": "Create card", "ja": "カードを作成", "zh": "创建会员卡"},
    "signup_hint": {"ko": "위에서부터 차례대로 입력하세요. * 표시는 필수 항목입니다.",
                    "en": "Fill in from top to bottom. * marks required fields.",
                    "ja": "上から順に入力してください。* は必須項目です。",
                    "zh": "请从上到下依次填写。* 为必填项。"},
    "lbl_name": {"ko": "이름 *", "en": "Name *", "ja": "お名前 *", "zh": "姓名 *"},
    "lbl_login_id": {"ko": "아이디 *", "en": "ID *", "ja": "ID *", "zh": "账号 *"},
    "lbl_password": {"ko": "비밀번호 *", "en": "Password *", "ja": "パスワード *", "zh": "密码 *"},
    "lbl_password2": {"ko": "비밀번호 재입력 *", "en": "Confirm password *", "ja": "パスワード (確認) *", "zh": "确认密码 *"},
    "ph_password2": {"ko": "비밀번호를 한 번 더 입력", "en": "Enter the password again",
                     "ja": "もう一度入力してください", "zh": "请再次输入密码"},
    "lbl_phone": {"ko": "전화번호 *", "en": "Phone *", "ja": "電話番号 *", "zh": "电话号码 *"},
    "lbl_allergy": {"ko": "알레르기 (선택)", "en": "Allergies (optional)", "ja": "アレルギー (任意)", "zh": "过敏原 (可选)"},
    "ph_allergy_search": {"ko": "검색 (예: 우유, 달걀, 견과)", "en": "Search (e.g. milk, egg, nut)",
                          "ja": "検索 (例: 牛乳、卵)", "zh": "搜索 (例: 牛奶、鸡蛋)"},
    "allergy_box": {"ko": "알레르기 선택 ▼ ({count}개 선택됨)", "en": "Choose allergies ▼ ({count} selected)",
                    "ja": "アレルギーを選択 ▼ ({count}件)", "zh": "选择过敏原 ▼ (已选{count}项)"},
    "allergy_chosen": {"ko": "선택: {items}", "en": "Selected: {items}", "ja": "選択: {items}", "zh": "已选: {items}"},
    "allergy_none": {"ko": "선택한 알레르기 없음", "en": "No allergies selected", "ja": "選択なし", "zh": "未选择过敏原"},
    "lbl_consent": {"ko": "약관 동의", "en": "Consent", "ja": "同意事項", "zh": "同意事项"},
    "lbl_face": {"ko": "얼굴 정보 등록 동의 (선택)", "en": "Face registration consent (optional)",
                 "ja": "顔情報の登録に同意 (任意)", "zh": "同意注册人脸信息 (可选)"},
    "face_consent_help": {"ko": "동의하면 다음 화면에서 얼굴을 등록합니다. 동의하지 않아도 비밀번호로 똑같이 이용할 수 있어요.",
                          "en": "If you agree, you will register your face on the next screen. Without it you can still use your password.",
                          "ja": "同意すると次の画面で顔を登録します。同意しなくてもパスワードで同じように利用できます。",
                          "zh": "同意后将在下一页注册人脸。不同意也可以用密码正常使用。"},
    "signup_next": {"ko": "다음 →", "en": "Next →", "ja": "次へ →", "zh": "下一步 →"},
    "signup_done": {"ko": "{nick}님의 회원 카드가 만들어졌습니다 (전화번호 {phone})",
                    "en": "Member card created for {nick} ({phone})",
                    "ja": "{nick}様の会員カードを作成しました ({phone})",
                    "zh": "已为 {nick} 创建会员卡 ({phone})"},
    "face_title": {"ko": "얼굴 등록", "en": "Face registration", "ja": "顔の登録", "zh": "人脸注册"},
    "face_target": {"ko": "등록할 회원: [bold]{nick}[/bold] ({login_id})", "en": "Member: [bold]{nick}[/bold] ({login_id})",
                    "ja": "登録する会員: [bold]{nick}[/bold] ({login_id})", "zh": "注册会员: [bold]{nick}[/bold] ({login_id})"},
    "face_guide": {"ko": "1. [카메라 켜고 등록 시작]을 누르면 큰 창이 열립니다. 왼쪽은 거울처럼 보이는 카메라, 오른쪽은 단계 안내예요.\n2. 얼굴을 왼쪽 화면의 타원 안에 맞추세요. 타원이 초록이면 맞는 위치입니다.\n3. 오른쪽에서 크게 강조된 단계대로 고개를 천천히 돌리거나 가까이 오세요. 맞게 하면 타원이 초록으로 바뀝니다.\n4. 마지막으로 정면을 보고 잠시 멈추면 끝납니다.\n5. 그만두려면 카메라 창에서 ESC를 누르세요. 사진은 저장하지 않고 얼굴 특징값만 암호화해 저장합니다.",
                   "en": "1. Press [Start camera] to open a large window: mirror camera on the left, steps on the right.\n2. Fit your face inside the oval on the left. A green oval means the position is right.\n3. Follow the highlighted step on the right: turn your head slowly or come closer. The oval turns green when you do it right.\n4. Finally look straight ahead and hold still.\n5. Press ESC in the camera window to cancel. No photos are stored, only encrypted face features.",
                   "ja": "1. [カメラを起動して登録]を押すと大きな画面が開きます。左は鏡のようなカメラ、右は手順の案内です。\n2. 左の画面の楕円に顔を合わせてください。楕円が緑なら正しい位置です。\n3. 右で大きく表示された手順どおりに、ゆっくり顔を向けるか近づいてください。正しくできると楕円が緑になります。\n4. 最後に正面を見て少し止まると完了です。\n5. 中止するにはカメラ画面で ESC を押してください。写真は保存せず、暗号化した特徴値だけを保存します。",
                   "zh": "1. 按[打开摄像头开始注册]后会打开大窗口：左边是镜像摄像头，右边是步骤提示。\n2. 把脸对准左边画面的椭圆。椭圆变绿表示位置正确。\n3. 按右边高亮的步骤慢慢转头或靠近。做对时椭圆会变绿。\n4. 最后看向正前方并稍停即可完成。\n5. 在摄像窗口按 ESC 可取消。不保存照片，只加密保存人脸特征值。"},
    "face_start": {"ko": "카메라 켜고 등록 시작", "en": "Start camera", "ja": "カメラを起動して登録", "zh": "打开摄像头开始注册"},
    "face_skip": {"ko": "나중에 하기 · 바로 주문", "en": "Later · order now", "ja": "後で · すぐ注文", "zh": "以后再说 · 直接点单"},
    "face_done": {"ko": "얼굴 등록 완료 · 다음부터 ID + 얼굴로 로그인할 수 있습니다.",
                  "en": "Face registered. Next time you can sign in with ID + face.",
                  "ja": "顔の登録が完了しました。次回から ID + 顔でログインできます。",
                  "zh": "人脸注册完成。下次可用 ID + 人脸登录。"},
    "face_later": {"ko": "얼굴 등록은 나중에 회원 로그인 화면의 [비밀번호 확인 후 얼굴 등록]으로 할 수 있어요.",
                   "en": "You can register your face later from the member sign-in screen.",
                   "ja": "顔の登録は後で会員ログイン画面から行えます。",
                   "zh": "以后可在会员登录页面注册人脸。"},
    "face_failed": {"ko": "얼굴 등록을 완료하지 못했습니다: {reason} · 다시 시도하거나 [나중에 하기]를 누르세요",
                    "en": "Face registration failed: {reason} · try again or press Later",
                    "ja": "顔の登録に失敗しました: {reason} · もう一度試すか「後で」を押してください",
                    "zh": "人脸注册失败: {reason} · 请重试或按“以后再说”"},
    # 03 메뉴 · 05 장바구니
    "menu_title": {"ko": "메뉴 선택", "en": "Choose your menu", "ja": "メニュー選択", "zh": "选择菜单"},
    "col_menu": {"ko": "메뉴", "en": "Item", "ja": "メニュー", "zh": "菜单"},
    "col_option": {"ko": "옵션", "en": "Options", "ja": "オプション", "zh": "选项"},
    "col_qty": {"ko": "수량", "en": "Qty", "ja": "数量", "zh": "数量"},
    "col_unit": {"ko": "단가", "en": "Unit", "ja": "単価", "zh": "单价"},
    "col_amount": {"ko": "금액", "en": "Amount", "ja": "金額", "zh": "金额"},
    "cart_delete": {"ko": "선택 삭제", "en": "Remove", "ja": "削除", "zh": "删除"},
    "cart_clear": {"ko": "전체 비우기", "en": "Clear all", "ja": "すべて削除", "zh": "全部清空"},
    "checkout": {"ko": "결제·혜택 확인 →", "en": "Checkout →", "ja": "お会計へ →", "zh": "去结算 →"},
    "sold_out": {"ko": "품절", "en": "Sold out", "ja": "売り切れ", "zh": "售罄"},
    "won": {"ko": "{n}원", "en": "₩{n}", "ja": "{n}ウォン", "zh": "{n}韩元"},
    "card_guest": {"ko": "비회원 주문 · 로그인 없이 이용 중 (포인트·쿠폰 적립 없음)",
                   "en": "Guest order · no sign-in (no points or coupons)",
                   "ja": "非会員注文 · ポイント・クーポンはありません", "zh": "非会员点单 · 不累积积分和优惠券"},
    "card_member": {"ko": "[bold]{nick}님[/bold] · 포인트 {points}P · 쿠폰 {coupons}장 · 방문 {visits}회 · 알레르기 {allergies}",
                    "en": "[bold]{nick}[/bold] · {points}P · {coupons} coupon(s) · {visits} visit(s) · allergies: {allergies}",
                    "ja": "[bold]{nick}様[/bold] · {points}P · クーポン{coupons}枚 · 来店{visits}回 · アレルギー: {allergies}",
                    "zh": "[bold]{nick}[/bold] · 积分 {points}P · 优惠券 {coupons}张 · 到店 {visits}次 · 过敏原: {allergies}"},
    "none": {"ko": "없음", "en": "none", "ja": "なし", "zh": "无"},
    "event_banner": {"ko": "🎉 진행 중 이벤트: {names}", "en": "🎉 Events now: {names}",
                     "ja": "🎉 開催中のイベント: {names}", "zh": "🎉 进行中的活动: {names}"},
    "cart_status": {"ko": "장바구니 {count}개 · 합계 {total}", "en": "Cart: {count} item(s) · total {total}",
                    "ja": "カート {count}点 · 合計 {total}", "zh": "购物车 {count}件 · 合计 {total}"},
    "added": {"ko": "{name} {qty}개를 담았습니다 · 합계 {total}", "en": "Added {qty} × {name} · total {total}",
              "ja": "{name}を{qty}点追加しました · 合計 {total}", "zh": "已加入 {name} × {qty} · 合计 {total}"},
    # 04 옵션
    "option_title": {"ko": "옵션 선택 · {name}", "en": "Options · {name}", "ja": "オプション選択 · {name}", "zh": "选择选项 · {name}"},
    "option_info": {"ko": "기본 가격 {price} · 재고 {stock}개 · 알레르기 유발 성분: {allergens}",
                    "en": "Base price {price} · {stock} left · allergens: {allergens}",
                    "ja": "基本価格 {price} · 在庫 {stock} · アレルゲン: {allergens}",
                    "zh": "基本价格 {price} · 库存 {stock} · 过敏原: {allergens}"},
    "allergy_warning": {"ko": "⚠ 알레르기 주의: {items} — 확인 후 담거나 취소하세요",
                        "en": "⚠ Allergy alert: {items} — confirm to add, or cancel",
                        "ja": "⚠ アレルギー注意: {items} — 確認して追加するか、キャンセルしてください",
                        "zh": "⚠ 过敏提醒: {items} — 请确认后加入或取消"},
    "size_option": {"ko": "{size} (+{price}원)", "en": "{size} (+₩{price})", "ja": "{size} (+{price}ウォン)", "zh": "{size} (+{price}韩元)"},
    "shot": {"ko": "샷 1회 추가 (+500원)", "en": "Extra shot (+₩500)", "ja": "ショット追加 (+500ウォン)", "zh": "加一份浓缩 (+500韩元)"},
    "syrup": {"ko": "시럽 추가 (+500원)", "en": "Add syrup (+₩500)", "ja": "シロップ追加 (+500ウォン)", "zh": "加糖浆 (+500韩元)"},
    "shot_short": {"ko": "샷 1회 추가", "en": "extra shot", "ja": "ショット追加", "zh": "加浓缩"},
    "syrup_short": {"ko": "시럽 추가", "en": "syrup", "ja": "シロップ", "zh": "糖浆"},
    "ph_qty": {"ko": "수량 (1~10)", "en": "Quantity (1-10)", "ja": "数量 (1〜10)", "zh": "数量 (1~10)"},
    "option_price": {"ko": "{unit} × {qty}개 = {total}", "en": "{unit} × {qty} = {total}",
                     "ja": "{unit} × {qty}点 = {total}", "zh": "{unit} × {qty} = {total}"},
    "add_to_cart": {"ko": "장바구니 담기", "en": "Add to cart", "ja": "カートに追加", "zh": "加入购物车"},
    "add_anyway": {"ko": "경고 확인 · 그래도 담기", "en": "I understand · add anyway", "ja": "確認して追加", "zh": "已知晓 · 仍然加入"},
    "cancel": {"ko": "취소", "en": "Cancel", "ja": "キャンセル", "zh": "取消"},
    # 06 혜택
    "benefit_title": {"ko": "쿠폰 · 포인트 사용", "en": "Coupons · Points", "ja": "クーポン · ポイント", "zh": "优惠券 · 积分"},
    "coupon_none": {"ko": "쿠폰 사용 안 함", "en": "No coupon", "ja": "クーポンを使わない", "zh": "不使用优惠券"},
    "ph_points": {"ko": "사용할 포인트 ({unit}P 단위, 1P = 1원)", "en": "Points to use ({unit}P steps, 1P = ₩1)",
                  "ja": "使用ポイント ({unit}P単位、1P = 1ウォン)", "zh": "使用积分 (以{unit}P为单位, 1P = 1韩元)"},
    "benefit_apply": {"ko": "혜택 적용 · 금액 갱신", "en": "Apply · update total", "ja": "適用 · 金額更新", "zh": "应用 · 更新金额"},
    "benefit_max": {"ko": "포인트 최대 사용", "en": "Use max points", "ja": "ポイントを最大使用", "zh": "最多使用积分"},
    "benefit_pay": {"ko": "이 금액으로 결제 →", "en": "Pay this amount →", "ja": "この金額で支払う →", "zh": "按此金额支付 →"},
    "benefit_skip": {"ko": "혜택 없이 결제", "en": "Pay without benefits", "ja": "特典なしで支払う", "zh": "不使用优惠支付"},
    "back_to_cart": {"ko": "장바구니로", "en": "Back to cart", "ja": "カートに戻る", "zh": "返回购物车"},
    "benefit_summary": {"ko": "보유 포인트 {balance}P · 쿠폰 {coupons}장\n할인 전 {total}  |  쿠폰 -{coupon}  |  포인트 -{points}\n[bold]할인 후 결제액 {final}[/bold]   (포인트 {unit}P 단위 · 최소 {min_use}P · 결제액의 {max_pct}%까지)",
                        "en": "Balance {balance}P · {coupons} coupon(s)\nSubtotal {total}  |  coupon -{coupon}  |  points -{points}\n[bold]To pay {final}[/bold]   (points in {unit}P steps · min {min_use}P · up to {max_pct}% of total)",
                        "ja": "保有ポイント {balance}P · クーポン{coupons}枚\n割引前 {total}  |  クーポン -{coupon}  |  ポイント -{points}\n[bold]お支払い {final}[/bold]   ({unit}P単位 · 最低{min_use}P · 支払額の{max_pct}%まで)",
                        "zh": "现有积分 {balance}P · 优惠券 {coupons}张\n折前 {total}  |  优惠券 -{coupon}  |  积分 -{points}\n[bold]应付 {final}[/bold]   (以{unit}P为单位 · 最少{min_use}P · 最多支付额的{max_pct}%)"},
    "benefit_applied": {"ko": "혜택을 적용했습니다.", "en": "Benefits applied.", "ja": "特典を適用しました。", "zh": "已应用优惠。"},
    # 07 현금 결제
    "payment_title": {"ko": "현금 결제", "en": "Cash payment", "ja": "現金でのお支払い", "zh": "现金支付"},
    "ph_cash": {"ko": "넣을 현금 (예: 5000)", "en": "Cash to insert (e.g. 5000)", "ja": "投入する現金 (例: 5000)", "zh": "投入现金 (例: 5000)"},
    "insert_cash": {"ko": "현금 넣기", "en": "Insert cash", "ja": "現金を入れる", "zh": "投入现金"},
    "pay": {"ko": "결제 완료", "en": "Complete payment", "ja": "支払い完了", "zh": "完成支付"},
    "refund": {"ko": "투입 취소 · 반환", "en": "Cancel · return cash", "ja": "取消 · 返金", "zh": "取消 · 退还现金"},
    "back": {"ko": "이전으로", "en": "Back", "ja": "戻る", "zh": "返回"},
    "pay_summary": {"ko": "결제 금액: [bold]{total}[/bold]   넣은 현금: [bold]{cash}[/bold]",
                    "en": "Amount due: [bold]{total}[/bold]   Inserted: [bold]{cash}[/bold]",
                    "ja": "お支払い金額: [bold]{total}[/bold]   投入金額: [bold]{cash}[/bold]",
                    "zh": "应付金额: [bold]{total}[/bold]   已投入: [bold]{cash}[/bold]"},
    "pay_enough": {"ko": "충분합니다 · 거스름돈 {change}", "en": "Enough · change {change}",
                   "ja": "十分です · おつり {change}", "zh": "金额足够 · 找零 {change}"},
    "pay_return": {"ko": "반환 예정: {detail}", "en": "Will return: {detail}", "ja": "お返し予定: {detail}", "zh": "将退还: {detail}"},
    "pay_short": {"ko": "{n} 더 넣어 주세요", "en": "Please insert {n} more", "ja": "あと{n}を入れてください", "zh": "请再投入 {n}"},
    "pay_short_error": {"ko": "현금이 {n} 부족합니다. 더 넣거나 투입 취소를 누르세요",
                        "en": "{n} short. Insert more cash or press Cancel",
                        "ja": "{n}不足しています。追加するか取消を押してください",
                        "zh": "还差 {n}。请继续投入或按取消"},
    "cash_inserted": {"ko": "{n}을 넣었습니다. 지금까지 {total}", "en": "Inserted {n}. Total so far {total}",
                      "ja": "{n}を投入しました。合計 {total}", "zh": "已投入 {n}。目前共 {total}"},
    "cash_returned": {"ko": "넣으신 현금 {n}을 반환했습니다.", "en": "Returned {n}.", "ja": "{n}をお返ししました。", "zh": "已退还 {n}。"},
    "no_cash": {"ko": "반환할 현금이 없습니다.", "en": "No cash to return.", "ja": "返金する現金はありません。", "zh": "没有可退还的现金。"},
    "refund_first": {"ko": "넣은 현금이 있습니다. 먼저 '투입 취소 · 반환'을 누르세요",
                     "en": "Cash is inserted. Press 'Cancel · return cash' first",
                     "ja": "投入済みの現金があります。先に「取消 · 返金」を押してください",
                     "zh": "已有投入的现金。请先按“取消 · 退还现金”"},
    "no_change": {"ko": "거스름돈 없음", "en": "no change", "ja": "おつりなし", "zh": "无找零"},
    "bill": {"ko": "{name} {n}장", "en": "{n} × {name}", "ja": "{name} {n}枚", "zh": "{name} {n}张"},
    "coin": {"ko": "{name} {n}개", "en": "{n} × {name}", "ja": "{name} {n}枚", "zh": "{name} {n}枚"},
    # 08 영수증
    "receipt_title": {"ko": "주문 완료", "en": "Order complete", "ja": "ご注文完了", "zh": "点单完成"},
    "receipt_head": {"ko": "[bold]주문번호 {id} · 준비 중[/bold]\n대기자: [bold]{who}[/bold]\n준비되면 주문번호로 안내해 드릴게요.",
                     "en": "[bold]Order {id} · preparing[/bold]\nName: [bold]{who}[/bold]\nWe will call your order number when it's ready.",
                     "ja": "[bold]注文番号 {id} · 準備中[/bold]\nお名前: [bold]{who}[/bold]\nご用意ができましたら番号でお呼びします。",
                     "zh": "[bold]订单号 {id} · 制作中[/bold]\n取餐人: [bold]{who}[/bold]\n制作完成后会按订单号叫号。"},
    "guest": {"ko": "비회원", "en": "Guest", "ja": "非会員", "zh": "非会员"},
    "receipt_total": {"ko": "합계 {total}", "en": "Subtotal {total}", "ja": "合計 {total}", "zh": "合计 {total}"},
    "receipt_discount": {"ko": "쿠폰 할인 -{coupon} · 포인트 사용 -{points} → 결제액 {final}",
                         "en": "Coupon -{coupon} · points -{points} → paid {final}",
                         "ja": "クーポン -{coupon} · ポイント -{points} → お支払い {final}",
                         "zh": "优惠券 -{coupon} · 积分 -{points} → 实付 {final}"},
    "receipt_cash": {"ko": "받은 돈 {cash} / 거스름돈 {change}\n반환: {detail}",
                     "en": "Received {cash} / change {change}\nReturned: {detail}",
                     "ja": "お預かり {cash} / おつり {change}\nお返し: {detail}",
                     "zh": "收款 {cash} / 找零 {change}\n退还: {detail}"},
    "receipt_member": {"ko": "이번 주문 적립 +{earned}P · 포인트 잔액 {points}P · 방문 {visits}회 · 보유 쿠폰 {coupons}장",
                       "en": "Earned +{earned}P · balance {points}P · {visits} visit(s) · {coupons} coupon(s)",
                       "ja": "今回の獲得 +{earned}P · 残高 {points}P · 来店{visits}回 · クーポン{coupons}枚",
                       "zh": "本次积分 +{earned}P · 余额 {points}P · 到店{visits}次 · 优惠券{coupons}张"},
    "receipt_event": {"ko": "이벤트 적용: {names}", "en": "Event applied: {names}", "ja": "イベント適用: {names}", "zh": "已参加活动: {names}"},
    "receipt_coupon": {"ko": "🎉 쿠폰 발행: {name}", "en": "🎉 New coupon: {name}", "ja": "🎉 クーポン発行: {name}", "zh": "🎉 获得优惠券: {name}"},
    "receipt_guest": {"ko": "비회원 주문 · 포인트·쿠폰 적립 없음", "en": "Guest order · no points or coupons",
                      "ja": "非会員注文 · ポイント・クーポンなし", "zh": "非会员点单 · 不累积积分和优惠券"},
    "next_customer": {"ko": "홈으로 돌아가기", "en": "Back to home", "ja": "ホームに戻る", "zh": "返回首页"},
    "paid_done": {"ko": "결제가 완료되었습니다. 영수증과 대기번호가 생성되었습니다.",
                  "en": "Payment complete. Your receipt and order number are ready.",
                  "ja": "お支払いが完了しました。レシートと番号を発行しました。",
                  "zh": "支付完成，已生成小票和订单号。"},
    # 상태 메시지
    "home_status": {"ko": "처음 화면입니다.", "en": "Home screen.", "ja": "ホーム画面です。", "zh": "首页。"},
    "returned_on_home": {"ko": "넣으신 현금 {n}을 반환합니다. ", "en": "Returning your {n}. ",
                         "ja": "投入された{n}をお返しします。", "zh": "退还您投入的 {n}。"},
    "next_waiting": {"ko": "다음 손님을 기다립니다.", "en": "Waiting for the next customer.",
                     "ja": "次のお客様をお待ちしています。", "zh": "等待下一位顾客。"},
    "login_face_ok": {"ko": "활성 생체 확인과 얼굴 인증이 완료되었습니다.", "en": "Liveness check and face sign-in complete.",
                      "ja": "生体確認と顔認証が完了しました。", "zh": "活体检测和人脸登录已完成。"},
    "login_pw_ok": {"ko": "비밀번호 인증이 완료되었습니다.", "en": "Password sign-in complete.",
                    "ja": "パスワード認証が完了しました。", "zh": "密码登录完成。"},
    "prefs_applied": {"ko": "회원 카드에 저장된 화면 설정을 적용했습니다.", "en": "Applied the display settings saved on your card.",
                      "ja": "会員カードに保存された表示設定を適用しました。", "zh": "已应用会员卡中保存的显示设置。"},
    "prefs_saved": {"ko": "화면 설정을 회원 카드에 저장했습니다.", "en": "Display settings saved to your member card.",
                    "ja": "表示設定を会員カードに保存しました。", "zh": "显示设置已保存到会员卡。"},
    "empty_cart": {"ko": "장바구니에 메뉴를 담아 주세요", "en": "Please add something to your cart",
                   "ja": "カートにメニューを入れてください", "zh": "请先将菜单加入购物车"},
    "pick_cart_row": {"ko": "장바구니에서 바꿀 메뉴를 먼저 선택하세요", "en": "Select a cart line first",
                      "ja": "先にカートの商品を選んでください", "zh": "请先选择购物车中的商品"},
}

CATEGORY_NAMES = {
    "커피": {"ko": "커피", "en": "Coffee", "ja": "コーヒー", "zh": "咖啡"},
    "논커피": {"ko": "논커피", "en": "Non-coffee", "ja": "ノンコーヒー", "zh": "非咖啡"},
    "차": {"ko": "차", "en": "Tea", "ja": "お茶", "zh": "茶"},
    "에이드": {"ko": "에이드", "en": "Ade", "ja": "エード", "zh": "气泡饮"},
    "디저트": {"ko": "디저트", "en": "Dessert", "ja": "デザート", "zh": "甜点"},
}

DENOMINATION_NAMES = {
    50000: {"ko": "오만원권", "en": "₩50,000 bill", "ja": "5万ウォン札", "zh": "5万韩元纸币"},
    10000: {"ko": "만원권", "en": "₩10,000 bill", "ja": "1万ウォン札", "zh": "1万韩元纸币"},
    5000: {"ko": "오천원권", "en": "₩5,000 bill", "ja": "5千ウォン札", "zh": "5千韩元纸币"},
    1000: {"ko": "천원권", "en": "₩1,000 bill", "ja": "千ウォン札", "zh": "1千韩元纸币"},
    500: {"ko": "500원", "en": "₩500 coin", "ja": "500ウォン硬貨", "zh": "500韩元硬币"},
    100: {"ko": "100원", "en": "₩100 coin", "ja": "100ウォン硬貨", "zh": "100韩元硬币"},
    50: {"ko": "50원", "en": "₩50 coin", "ja": "50ウォン硬貨", "zh": "50韩元硬币"},
    10: {"ko": "10원", "en": "₩10 coin", "ja": "10ウォン硬貨", "zh": "10韩元硬币"},
    1: {"ko": "1원", "en": "₩1", "ja": "1ウォン", "zh": "1韩元"},
}

MENU_NAMES_EN = {
    "아메리카노": "Americano", "카페라떼": "Caffe Latte", "바닐라라떼": "Vanilla Latte",
    "카푸치노": "Cappuccino", "카페모카": "Caffe Mocha", "카라멜마키아토": "Caramel Macchiato",
    "콜드브루": "Cold Brew", "연유라떼": "Condensed Milk Latte", "헤이즐넛라떼": "Hazelnut Latte",
    "디카페인 아메리카노": "Decaf Americano", "초코라떼": "Chocolate Latte", "딸기라떼": "Strawberry Latte",
    "고구마라떼": "Sweet Potato Latte", "말차라떼": "Matcha Latte", "밀크티": "Milk Tea",
    "곡물라떼": "Grain Latte", "민트초코": "Mint Chocolate", "흑임자라떼": "Black Sesame Latte",
    "망고라떼": "Mango Latte", "블루베리라떼": "Blueberry Latte", "유자차": "Citron Tea",
    "레몬차": "Lemon Tea", "자몽차": "Grapefruit Tea", "캐모마일": "Chamomile", "페퍼민트": "Peppermint",
    "얼그레이": "Earl Grey", "루이보스": "Rooibos", "히비스커스": "Hibiscus", "녹차": "Green Tea",
    "복숭아 아이스티": "Peach Iced Tea", "레몬에이드": "Lemonade", "자몽에이드": "Grapefruit Ade",
    "청포도에이드": "Green Grape Ade", "딸기에이드": "Strawberry Ade", "망고에이드": "Mango Ade",
    "블루레몬에이드": "Blue Lemonade", "패션후르츠에이드": "Passion Fruit Ade", "체리에이드": "Cherry Ade",
    "매실에이드": "Plum Ade", "수박에이드": "Watermelon Ade", "크루아상": "Croissant",
    "초코쿠키": "Chocolate Cookie", "마카롱": "Macaron", "치즈케이크": "Cheesecake", "티라미수": "Tiramisu",
    "베이글": "Bagel", "소금빵": "Salt Bread", "브라우니": "Brownie", "와플": "Waffle", "샌드위치": "Sandwich",
}


ALLERGEN_NAMES = {
    "알류(달걀 등)": ("Eggs", "卵", "蛋类"), "우유": ("Milk", "乳", "牛奶"), "메밀": ("Buckwheat", "そば", "荞麦"),
    "땅콩": ("Peanut", "落花生", "花生"), "대두": ("Soybean", "大豆", "大豆"), "밀": ("Wheat", "小麦", "小麦"),
    "고등어": ("Mackerel", "さば", "鲭鱼"), "게": ("Crab", "かに", "螃蟹"), "새우": ("Shrimp", "えび", "虾"),
    "돼지고기": ("Pork", "豚肉", "猪肉"), "복숭아": ("Peach", "もも", "桃子"), "토마토": ("Tomato", "トマト", "番茄"),
    "아황산류": ("Sulfites", "亜硫酸塩", "亚硫酸盐"), "호두": ("Walnut", "くるみ", "核桃"),
    "닭고기": ("Chicken", "鶏肉", "鸡肉"), "쇠고기": ("Beef", "牛肉", "牛肉"), "오징어": ("Squid", "いか", "鱿鱼"),
    "조개류(굴·전복·홍합 포함)": ("Shellfish (oyster, abalone, mussel)", "貝類 (かき・あわび・ムール貝)", "贝类 (牡蛎·鲍鱼·贻贝)"),
    "잣": ("Pine nut", "松の実", "松子"),
    "기타 견과류(헤이즐넛·아몬드 등)": ("Other tree nuts (hazelnut, almond)", "その他ナッツ類 (ヘーゼルナッツ等)", "其他坚果 (榛子·杏仁等)"),
    "참깨": ("Sesame", "ごま", "芝麻"),
}


def allergen_name(lang: str, name: str) -> str:
    names = ALLERGEN_NAMES.get(name)
    if lang == "ko" or not names:
        return name
    return names[{"en": 0, "ja": 1, "zh": 2}.get(lang, 0)]


def t(lang: str, key: str, **values) -> str:
    entry = TEXT[key]
    template = entry.get(lang) or entry[DEFAULT_LANGUAGE]
    return template.format(**values) if values else template


def won(lang: str, amount: int) -> str:
    return t(lang, "won", n=f"{amount:,}")


def category_name(lang: str, category: str) -> str:
    names = CATEGORY_NAMES.get(category)
    return (names.get(lang) or category) if names else category


def menu_name(lang: str, item: dict) -> str:
    if lang == "ko":
        return item["name"]
    return item.get("name_en") or MENU_NAMES_EN.get(item["name"], item["name"])


def option_text(lang: str, options: dict) -> str:
    if not options:
        return "-"
    parts = [options["temperature"], options["size"]]
    parts += [t(lang, f"{extra}_short") for extra in options["extras"]]
    return " / ".join(parts)


def change_text(lang: str, breakdown: dict) -> str:
    if not breakdown:
        return t(lang, "no_change")
    parts = []
    for unit, count in sorted(breakdown.items(), key=lambda pair: -int(pair[0])):
        unit = int(unit)
        name = DENOMINATION_NAMES[unit].get(lang) or DENOMINATION_NAMES[unit]["ko"]
        parts.append(t(lang, "bill" if unit >= 1000 else "coin", name=name, n=count))
    return " · ".join(parts)


def missing_translations() -> list[str]:
    """빠진 번역 목록 (테스트에서 0개인지 확인한다)."""
    return [f"{key}:{lang}" for key, entry in TEXT.items() for lang in LANGUAGES if not entry.get(lang)]
