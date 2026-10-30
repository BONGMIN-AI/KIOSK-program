"""승차권 탭(T1): 시간표·좌석·요금·혜택 계산과 예매표 조회. 시연용 가짜 데이터라 메모리에만 있다.

실제 버스 회사와 연결하지 않는다. 시간표는 날짜·도착지로 늘 같은 모양으로 만들고, 이미 팔린 좌석도
차 번호로 정해지는 의사 난수라 다시 열어도 같다. 이 키오스크에서 산 좌석·출력한 예매는 프로그램이 켜져
있는 동안만 기억한다.

요금 규칙(시연 값):
- 어른 요금이 기준. 중고생 80% · 초등생 50%.
- 혜택(경로·보훈·군인·장애인)은 승객마다 하나. 승객 종류 할인과 겹치지 않고 더 싼 쪽을 쓴다.
- 100원 아래는 버린다.
- 승차권은 카페 쿠폰·포인트 할인과 적립에서 빠진다 (OrderSession·complete_order가 따로 더한다).

출발지는 이 터미널(서울경부)이 기본이지만 다른 터미널도 고를 수 있다. 서울경부 노선은 아래 표 값,
나머지 노선은 터미널 사이 거리로 요금·시간을 어림한 시연 값이다.
회원이 '저장'을 고른 노선은 회원 카드 extra["saved_routes"]에 모여 My Menu에 보인다.
"""
import random
import zlib
from datetime import date, datetime, time, timedelta

ORIGIN = "서울경부"
SALES_CLOSE_MINUTES = 10       # 출발 10분 전 판매·출력 마감
HOLD_SECONDS = 5 * 60          # 고른 좌석을 잡아 두는 시간
MAX_PASSENGERS = 6
DAYS_AHEAD = 7                 # 오늘부터 7일
WEEKDAYS = "월화수목금토일"
GRADES = {"우등": 28, "일반": 45}
COMPANIES = ["금호", "동양", "중앙", "천일"]
PASSENGER_TYPES = {"어른": 100, "중고생": 80, "초등생": 50}          # 어른 요금의 몇 %
BENEFITS = {"없음": 0, "경로": 30, "보훈": 30, "군인": 20, "장애인": 50}  # 할인 %
NORMAL_RATE = 74               # 일반 요금 = 우등의 74%

# (도착지, 우등 어른 요금, 걸리는 분, 배차 간격 분, 승차장)
DESTINATIONS = [
    ("대전복합", 13700, 120, 30, 3),
    ("대전청사", 13700, 125, 60, 3),
    ("대전도룡", 13900, 130, 60, 4),
    ("천안", 9200, 70, 30, 5),
    ("청주", 11700, 100, 30, 5),
    ("세종", 12600, 110, 60, 4),
    ("공주", 13000, 115, 60, 6),
    ("전주", 20800, 165, 30, 7),
    ("광주", 30600, 210, 30, 8),
    ("동대구", 30700, 220, 30, 9),
    ("부산", 39400, 260, 30, 10),
    ("진주", 33300, 230, 60, 11),
    ("포항", 33500, 250, 60, 12),
]
DESTINATION_NAMES = [row[0] for row in DESTINATIONS]
TERMINAL_NAMES = [ORIGIN] + DESTINATION_NAMES
# 서울경부를 (0, 0)으로 둔 대략의 위치 (동쪽 x, 북쪽 y, km). 서울경부가 아닌 노선의 요금·시간을 어림한다.
POSITIONS = {
    "서울경부": (0, 0), "천안": (10, -85), "대전복합": (25, -140), "대전청사": (20, -138),
    "대전도룡": (22, -132), "청주": (45, -110), "세종": (10, -120), "공주": (-15, -125),
    "전주": (-10, -195), "광주": (-60, -270), "동대구": (130, -210), "부산": (165, -290),
    "진주": (85, -280), "포항": (205, -200),
}
ROAD_FACTOR = 1.3              # 직선거리 -> 도로 거리
FARE_PER_KM = 75               # 우등 어른 요금 (원/km, 시연 값)


def route_info(origin, destination):
    """노선 (우등 어른 요금, 걸리는 분, 배차 간격 분, 승차장, 순번)."""
    if origin not in TERMINAL_NAMES or destination not in TERMINAL_NAMES:
        raise ValueError("터미널을 목록에서 골라 주세요")
    if origin == destination:
        raise ValueError("출발지와 도착지가 같아요")
    if ORIGIN in (origin, destination):              # 서울경부 노선은 표 값 (돌아오는 길도 같은 값)
        other = destination if origin == ORIGIN else origin
        index = DESTINATION_NAMES.index(other)
        _, base, minutes, every, platform = DESTINATIONS[index]
        return base, minutes, every, platform, index
    (x1, y1), (x2, y2) = POSITIONS[origin], POSITIONS[destination]
    km = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 * ROAD_FACTOR
    base = max(4000, round(km * FARE_PER_KM / 100) * 100)
    minutes = round((km / 85 * 60 + 15) / 5) * 5
    index = zlib.crc32(f"{origin}|{destination}".encode("utf-8"))
    return base, minutes, 60, index % 12 + 1, index


def seat_rows(grade):
    """좌석 배치 (와이어프레임 T1-5). None은 통로. 운전석은 왼쪽 앞, 출입구는 오른쪽 앞.

    일반 45석: 2 + 통로 + 2, 10줄(1~40) + 맨 뒤 5석. 우등 28석: 2 + 통로 + 1, 8줄(1~24) + 맨 뒤 4석
    (맨 뒷줄 27번은 26번과 28번 사이 통로 자리).
    """
    if grade == "일반":
        rows = [[n, n + 1, None, n + 2, n + 3] for n in range(1, 41, 4)]
        return rows + [[41, 42, 43, 44, 45]]
    rows = [[n, n + 1, None, None, n + 2] for n in range(1, 25, 3)]
    return rows + [[25, 26, 27, None, 28]]


def all_seats(grade):
    return sorted(seat for row in seat_rows(grade) for seat in row if seat)


def fare(adult_fare, kind="어른", benefit="없음"):
    """승객 한 명 요금. 승객 종류 할인과 혜택 할인 중 더 큰 쪽만 쓴다."""
    if kind not in PASSENGER_TYPES:
        raise ValueError(f"없는 승객 종류입니다: {kind}")
    if benefit not in BENEFITS:
        raise ValueError(f"없는 혜택입니다: {benefit}")
    percent = min(PASSENGER_TYPES[kind], 100 - BENEFITS[benefit])
    return adult_fare * percent // 100 // 100 * 100


def assign_passengers(counts, seats):
    """{'어른': 2, '중고생': 1} + 고른 좌석 -> 좌석마다 승객 (어른부터, 좌석 번호 순)."""
    kinds = [kind for kind in PASSENGER_TYPES for _ in range(counts.get(kind, 0))]
    if len(kinds) != len(seats):
        raise ValueError(f"좌석 {len(kinds)}개를 골라 주세요")
    return [{"seat": seat, "type": kind, "benefit": "없음"} for seat, kind in zip(sorted(seats), kinds)]


def quote(adult_fare, passengers):
    """승객마다 요금을 붙인 새 목록과 합계."""
    priced = [dict(p, price=fare(adult_fare, p["type"], p["benefit"])) for p in passengers]
    return priced, sum(p["price"] for p in priced)


def depart_text(iso):
    """'2026-10-29T18:30' -> '10/29(목) 18:30'"""
    moment = datetime.fromisoformat(iso)
    return f"{moment.month}/{moment.day}({WEEKDAYS[moment.weekday()]}) {moment:%H:%M}"


def day_text(day, today):
    """날짜 칩 글자: '오늘 10/31' · '내일 11/1' · '모레 11/2' · '11/3(화)'"""
    word = {0: "오늘", 1: "내일", 2: "모레"}.get((day - today).days)
    if word:
        return f"{word} {day.month}/{day.day}"
    return f"{day.month}/{day.day}({WEEKDAYS[day.weekday()]})"


def until_text(depart, now):
    """출발까지 남은 시간 말."""
    minutes = int((depart - now).total_seconds() // 60)
    if minutes < 0:
        return "출발함"
    if minutes < 60:
        return f"출발 {minutes}분 전"
    if depart.date() == now.date():
        return f"출발 {minutes // 60}시간 {minutes % 60}분 전"
    return f"{(depart.date() - now.date()).days}일 뒤"


def search_terminals(query, exclude=None):
    """글자·초성으로 터미널 찾기. exclude(예: 이미 고른 출발지)는 빼고."""
    from .hangul import matches
    return [name for name in TERMINAL_NAMES if name != exclude and matches(name, query)]


def search_destinations(query, origin=ORIGIN):
    return search_terminals(query, exclude=origin)


# 저장한 노선 (회원 My Menu)
def saved_routes(customer):
    """회원이 저장한 노선, 최근에 쓴 순."""
    if not customer:
        return []
    routes = customer["extra"].get("saved_routes", [])
    return sorted(routes, key=lambda r: r.get("last", ""), reverse=True)


def is_saved(customer, origin, destination):
    return any(r["origin"] == origin and r["destination"] == destination for r in saved_routes(customer))


def remember_route(customer, origin, destination, when):
    """노선을 저장하거나, 이미 있으면 이용 횟수·최근 날짜를 고친다 (회원 카드만 바꾼다)."""
    routes = customer["extra"].setdefault("saved_routes", [])
    for route in routes:
        if route["origin"] == origin and route["destination"] == destination:
            route["times"] = route.get("times", 0) + 1
            route["last"] = when
            return route
    route = {"origin": origin, "destination": destination, "times": 1, "last": when}
    routes.append(route)
    return route


def forget_route(vault, customer_id, origin, destination):
    """저장한 노선을 지운다 (금고에 바로 저장)."""
    customers = vault.read("customers", default={})
    extra = customers[customer_id]["extra"]
    extra["saved_routes"] = [r for r in extra.get("saved_routes", [])
                             if not (r["origin"] == origin and r["destination"] == destination)]
    vault.write("customers", customers)


def ticket_summary(item):
    """장바구니·영수증용 한 줄: '10/29(목) 18:30 우등 · 7·8번'"""
    seats = "·".join(str(p["seat"]) for p in item["passengers"])
    return f"{depart_text(item['depart'])} {item['grade']} · {seats}번"


class TicketOffice:
    """승차권 위탁 판매소 한 곳. 시간표는 계산으로 만들고, 판 좌석·잡아 둔 좌석·예매는 메모리에 둔다."""

    def __init__(self, now=None):
        now = now or datetime.now()
        self.sold = {}          # 차 번호 -> 이 키오스크에서 판 좌석
        self.holds = {}         # 잡아 둔 번호 -> {"bus_id", "seats", "until"}
        self.next_hold = 1
        self.reservations = {}  # 예매번호 -> 예매
        self.seed_reservations(now)

    # 시간표
    def buses_on(self, origin, destination, day):
        """그날 그 노선의 모든 차 (정적인 정보만)."""
        base, minutes, every, platform, index = route_info(origin, destination)
        first = datetime.combine(day, time(6, 0)) + timedelta(minutes=index * 5 % every)
        last = datetime.combine(day, time(22, 30))
        buses, depart, number = [], first, 0
        while depart <= last:
            grade = "우등" if number % 2 == 0 else "일반"
            buses.append({
                "id": f"{day.isoformat()}|{origin}|{destination}|{depart:%H:%M}",
                "origin": origin, "destination": destination,
                "depart": depart.isoformat(timespec="minutes"),
                "arrive": (depart + timedelta(minutes=minutes)).isoformat(timespec="minutes"),
                "grade": grade, "company": COMPANIES[(index + number) % len(COMPANIES)],
                "platform": platform, "seats_total": GRADES[grade],
                "fare": base if grade == "우등" else base * NORMAL_RATE // 100 // 100 * 100,
            })
            depart += timedelta(minutes=every)
            number += 1
        return buses

    def bus(self, bus_id, now=None):
        day, origin, destination, _ = bus_id.split("|")
        for bus in self.buses_on(origin, destination, date.fromisoformat(day)):
            if bus["id"] == bus_id:
                return self.with_status(bus, now or datetime.now())
        raise ValueError("없는 차편입니다")

    def timetable(self, destination, day, now=None, origin=ORIGIN):
        """고른 날짜의 아직 출발하지 않은 차. 마감(출발 10분 전)·매진도 흐리게 보여 주려고 넣는다."""
        now = now or datetime.now()
        if destination not in TERMINAL_NAMES:
            raise ValueError("도착지를 목록에서 골라 주세요")
        if origin not in TERMINAL_NAMES:
            raise ValueError("출발지를 목록에서 골라 주세요")
        buses = [self.with_status(bus, now) for bus in self.buses_on(origin, destination, day)]
        return [bus for bus in buses if bus["status"] != "departed"]

    def with_status(self, bus, now):
        bus = dict(bus)
        left = datetime.fromisoformat(bus["depart"]) - now
        bus["seats_left"] = bus["seats_total"] - len(self.taken(bus["id"], now, bus["grade"]))
        if left.total_seconds() < 0:
            bus["status"] = "departed"
        elif left < timedelta(minutes=SALES_CLOSE_MINUTES):
            bus["status"] = "closed"
        elif bus["seats_left"] <= 0:
            bus["status"] = "sold_out"
        else:
            bus["status"] = "ok"
        return bus

    # 좌석
    @staticmethod
    def booked_elsewhere(bus_id, grade):
        """다른 곳(인터넷·매표소)에서 이미 팔린 좌석. 차 번호로 정해지는 시연 값 (약 8%는 매진)."""
        rng = random.Random(zlib.crc32(bus_id.encode("utf-8")))
        seats = all_seats(grade)
        if rng.random() < 0.08:
            return set(seats)
        return set(rng.sample(seats, rng.randint(0, len(seats) * 6 // 10)))

    def taken(self, bus_id, now=None, grade=None):
        """앉을 수 없는 좌석: 다른 곳에서 팔림 + 여기서 팔림 + 잡아 둔 좌석."""
        now = now or datetime.now()
        grade = grade or self.bus(bus_id, now)["grade"]
        result = self.booked_elsewhere(bus_id, grade) | self.sold.get(bus_id, set())
        for hold in self.holds.values():
            if hold["bus_id"] == bus_id and hold["until"] > now:
                result |= set(hold["seats"])
        return result

    def hold(self, bus_id, seats, now=None):
        """고른 좌석을 5분 잡아 둔다. 그 사이 다른 손님은 못 고른다. 안 되면 ValueError."""
        now = now or datetime.now()
        bus = self.bus(bus_id, now)
        if bus["status"] == "closed":
            raise ValueError("출발 10분 전이라 판매가 마감됐어요 · 다른 시간을 골라 주세요")
        if bus["status"] == "departed":
            raise ValueError("이미 출발한 차예요 · 다른 시간을 골라 주세요")
        seats = sorted(int(seat) for seat in seats)
        if not seats:
            raise ValueError("좌석을 골라 주세요")
        if len(seats) > MAX_PASSENGERS:
            raise ValueError(f"한 번에 {MAX_PASSENGERS}석까지 살 수 있어요")
        if any(seat not in all_seats(bus["grade"]) for seat in seats):
            raise ValueError("없는 좌석입니다")
        busy = set(seats) & self.taken(bus_id, now, bus["grade"])
        if busy:
            raise ValueError(f"{', '.join(map(str, sorted(busy)))}번 좌석은 방금 팔렸어요 · 다른 좌석을 골라 주세요")
        hold_id = f"H{self.next_hold:04d}"
        self.next_hold += 1
        self.holds[hold_id] = {"bus_id": bus_id, "seats": seats, "until": now + timedelta(seconds=HOLD_SECONDS)}
        return hold_id

    def hold_seconds(self, hold_id, now=None):
        """잡아 둔 좌석의 남은 초 (없거나 지났으면 0)."""
        hold = self.holds.get(hold_id)
        if hold is None:
            return 0
        return max(0, int((hold["until"] - (now or datetime.now())).total_seconds()))

    def release(self, hold_id):
        self.holds.pop(hold_id, None)

    def check_hold(self, hold_id, now=None):
        if not self.hold_seconds(hold_id, now):
            raise ValueError("좌석을 잡아 둔 5분이 지났어요 · 승차권을 다시 골라 주세요")

    def confirm(self, hold_id, now=None):
        """결제가 끝나면 잡아 둔 좌석을 판 좌석으로 바꾼다."""
        self.check_hold(hold_id, now)
        hold = self.holds.pop(hold_id)
        self.sold.setdefault(hold["bus_id"], set()).update(hold["seats"])

    def make_item(self, bus, passengers, hold_id):
        """장바구니에 담는 승차권 한 묶음 (저장할 수 있게 글자·숫자만)."""
        priced, total = quote(bus["fare"], passengers)
        return {
            "hold_id": hold_id, "bus_id": bus["id"], "origin": bus["origin"],
            "destination": bus["destination"], "depart": bus["depart"], "grade": bus["grade"],
            "company": bus["company"], "platform": bus["platform"],
            "passengers": priced, "count": len(priced), "total": total,
        }

    # 예매표 출력
    def first_bus_after(self, destination, moment):
        for offset in range(DAYS_AHEAD + 1):
            for bus in self.buses_on(ORIGIN, destination, moment.date() + timedelta(days=offset)):
                if datetime.fromisoformat(bus["depart"]) >= moment:
                    return bus
        raise ValueError("차편이 없습니다")

    def seed_reservations(self, now):
        """인터넷·앱으로 예매해 둔 표 (시연). 지금 시각 기준으로 만든다."""
        soon = self.first_bus_after("대전복합", now + timedelta(minutes=30))
        later = self.first_bus_after("동대구", datetime.combine(now.date() + timedelta(days=2), time(18, 0)))
        printed = self.first_bus_after("부산", now + timedelta(hours=3))
        rows = [
            ("12345678", "홍길동", "900101", soon, [7, 8]),
            ("23456789", "홍길동", "900101", later, [11]),
            ("34567890", "김공학", "010315", printed, [20]),
        ]
        for number, name, birth, bus, seats in rows:
            self.reservations[number] = {
                "number": number, "name": name, "birth": birth, "origin": bus["origin"],
                "destination": bus["destination"], "depart": bus["depart"], "grade": bus["grade"],
                "company": bus["company"], "platform": bus["platform"], "seats": seats, "printed": False}
            self.sold.setdefault(bus["id"], set()).update(seats)
        self.reservations["34567890"]["printed"] = True
        gone = (now - timedelta(minutes=40)).replace(second=0, microsecond=0)
        self.reservations["45678901"] = {
            "number": "45678901", "name": "김공학", "birth": "010315", "origin": ORIGIN,
            "destination": "천안", "depart": gone.isoformat(timespec="minutes"), "grade": "일반",
            "company": "동양", "platform": 5, "seats": [3], "printed": False}

    def lookup(self, number=None, name=None, birth=None, now=None):
        """예매번호 또는 이름 + 생년월일 6자리로 출력할 수 있는 예매를 찾는다. 없으면 이유를 담은 ValueError."""
        now = now or datetime.now()
        if number is not None:
            number = number.replace("-", "").strip()
            if not number:
                raise ValueError("예매번호를 입력해 주세요")
            found = [self.reservations[number]] if number in self.reservations else []
        else:
            name, birth = (name or "").strip(), (birth or "").strip()
            if not name or len(birth) != 6 or not birth.isdigit():
                raise ValueError("이름과 생년월일 6자리를 입력해 주세요 (예: 900101)")
            found = [r for r in self.reservations.values() if r["name"] == name and r["birth"] == birth]
        if not found:
            raise ValueError("조회된 예매가 없어요 · 입력한 내용을 확인해 주세요")
        usable, reasons = [], []
        for reservation in found:
            depart = datetime.fromisoformat(reservation["depart"])
            if reservation["printed"]:
                reasons.append("이미 출력한 표예요")
            elif depart - now < timedelta(minutes=SALES_CLOSE_MINUTES):
                reasons.append("출발 시간이 지났어요 (출발 10분 전까지 출력)")
            else:
                usable.append(reservation)
        if not usable:
            raise ValueError(" · ".join(dict.fromkeys(reasons)) + " · 매표소에 문의해 주세요")
        return sorted(usable, key=lambda r: r["depart"])

    def print_reservations(self, numbers, now=None):
        """고른 예매를 출력했다고 표시하고 그 예매들을 돌려준다."""
        now = now or datetime.now()
        if not numbers:
            raise ValueError("출력할 표를 골라 주세요")
        result = []
        for number in numbers:
            reservation = self.reservations.get(number)
            if reservation is None:
                raise ValueError("조회된 예매가 없어요")
            self.lookup(number=number, now=now)       # 그 사이 마감·출력됐으면 여기서 멈춘다
            result.append(reservation)
        for reservation in result:
            reservation["printed"] = True
        return result
