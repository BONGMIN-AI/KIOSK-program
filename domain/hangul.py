"""화면 한글 키보드용 글자 조합과 초성 검색. 파일·화면에 접근하지 않는 순수 함수만 둔다.

type_jamo("기", "ㅁ") -> "김", type_jamo("김", "ㅏ") -> "기마" 처럼 두벌식 자판으로 누른 자모를 글자로 합친다.
matches("대전복합", "대ㅈ") -> True: 글자 그대로 또는 초성으로 앞부분이 맞으면 후보로 보여 준다.
"""

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ",
        "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
VOWEL_PAIRS = {("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ", ("ㅜ", "ㅓ"): "ㅝ",
               ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ", ("ㅡ", "ㅣ"): "ㅢ"}
FINAL_PAIRS = {("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ", ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ",
               ("ㄹ", "ㅂ"): "ㄼ", ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ", ("ㄹ", "ㅎ"): "ㅀ",
               ("ㅂ", "ㅅ"): "ㅄ"}
FINAL_SPLIT = {pair: parts for parts, pair in FINAL_PAIRS.items()}


def split(char):
    """완성된 한 글자 -> (초성, 중성, 종성). 한글 글자가 아니면 None."""
    if not char or not "가" <= char <= "힣":
        return None
    code = ord(char) - 0xAC00
    return CHO[code // 588], JUNG[code % 588 // 28], JONG[code % 28]


def join(cho, jung, jong=""):
    return chr(0xAC00 + (CHO.index(cho) * 21 + JUNG.index(jung)) * 28 + JONG.index(jong))


def type_jamo(text, key):
    """text 끝에 자모 key를 눌렀을 때의 새 글자들."""
    head, last = text[:-1], text[-1:]
    parts = split(last)
    if key in JUNG:
        if last in CHO:
            return head + join(last, key)
        if parts:
            cho, jung, jong = parts
            if not jong:
                pair = VOWEL_PAIRS.get((jung, key))
                return head + join(cho, pair) if pair else text + key
            if jong in FINAL_SPLIT:          # 겹받침은 뒤 자음만 다음 글자로 넘긴다 (닭 + ㅏ -> 달가)
                first, second = FINAL_SPLIT[jong]
                return head + join(cho, jung, first) + join(second, key)
            if jong in CHO:                  # 받침이 다음 글자 첫소리로 넘어간다 (김 + ㅏ -> 기마)
                return head + join(cho, jung) + join(jong, key)
        if last in JUNG and (last, key) in VOWEL_PAIRS:
            return head + VOWEL_PAIRS[(last, key)]
        return text + key
    if parts:
        cho, jung, jong = parts
        if not jong and key in JONG:
            return head + join(cho, jung, key)
        if jong and (jong, key) in FINAL_PAIRS:
            return head + join(cho, jung, FINAL_PAIRS[(jong, key)])
    return text + key


def erase(text):
    """한 번 지우기: 받침 → 모음 → 글자 순서로 조금씩 지운다."""
    parts = split(text[-1:])
    if not parts:
        return text[:-1]
    cho, jung, jong = parts
    if jong:
        smaller = FINAL_SPLIT.get(jong, ("",))[0]
        return text[:-1] + join(cho, jung, smaller)
    return text[:-1] + cho


def initial(char):
    parts = split(char)
    return parts[0] if parts else char


def matches(name, query):
    """query가 name의 앞부분과 맞는지. 각 글자는 그대로 같거나, 초성 하나로 써도 된다.

    아직 조합 중인 마지막 글자의 받침은 다음 글자의 초성일 수도 있다 (대전의 '댖' = '대ㅈ').
    """
    query = query.replace(" ", "")
    if not query:
        return True
    variants = [query]
    parts = split(query[-1])
    if parts and parts[2] in CHO:
        variants.append(query[:-1] + join(parts[0], parts[1]) + parts[2])
    for variant in variants:
        if len(variant) <= len(name) and all(
                q == n or (q in CHO and initial(n) == q) for q, n in zip(variant, name)):
            return True
    return False
