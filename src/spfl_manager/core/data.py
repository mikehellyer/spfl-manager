"""Static league data: the four SPFL divisions and their clubs (2026/27 line-up).

Each club has a name, a short code, its kit (shirt colour, shorts colour and an
optional stripes/hoops pattern with a second shirt colour), its ground, the ground's
capacity and a base rating (0-100) that sets how strong its players are.
Real squads live in squads.json. Edit these files to change the leagues.
"""

from typing import NamedTuple

DIVISIONS = ["Premiership", "Championship", "League One", "League Two"]
DIVISION_FULL = [
    "SPFL Premiership",
    "SPFL Championship",
    "SPFL League One",
    "SPFL League Two",
]

# Games per season: 12-team Premiership plays 3 rounds (33 games),
# the 10-team divisions play 4 rounds (36 games).
LEAGUE_CYCLES = {12: 3, 10: 4}

WHITE = (240, 240, 240)
BLACK = (20, 20, 20)
NAVY = (24, 17, 70)
RED = (210, 20, 30)
BLUE = (0, 68, 255)
ROYAL = (20, 50, 200)


class ClubInfo(NamedTuple):
    name: str
    short: str
    shirt: tuple
    shorts: tuple
    stadium: str
    capacity: int
    rating: int
    pattern: str = ""  # "", "stripes" or "hoops"
    shirt2: tuple = WHITE


C = ClubInfo
CLUBS = [
    # ---------------- Premiership ----------------
    [
        C("Celtic", "CEL", (0, 135, 81), WHITE, "Celtic Park", 60411, 80, "hoops", WHITE),
        C("Rangers", "RAN", ROYAL, WHITE, "Ibrox Stadium", 51700, 78),
        C("Heart of Midlothian", "HEA", (96, 31, 46), WHITE, "Tynecastle Park", 19852, 67),
        C("Aberdeen", "ABE", RED, RED, "Pittodrie Stadium", 19274, 66),
        C("Hibernian", "HIB", (0, 110, 60), WHITE, "Easter Road", 20421, 65),
        C("Dundee United", "DUN", (241, 102, 34), BLACK, "Tannadice Park", 14223, 61),
        C("Motherwell", "MOT", (255, 190, 0), WHITE, "Fir Park", 13677, 60),
        C("Kilmarnock", "KIL", ROYAL, WHITE, "Rugby Park", 15003, 60, "stripes", WHITE),
        C("St Mirren", "STM", BLACK, BLACK, "St Mirren Park", 8000, 59, "stripes", WHITE),
        C("Dundee", "DND", (23, 38, 67), WHITE, "Dens Park", 11775, 58),
        C("Falkirk", "FAL", (0, 0, 102), WHITE, "Falkirk Stadium", 7937, 58),
        C("St Johnstone", "STJ", BLUE, BLUE, "McDiarmid Park", 10696, 57),
    ],
    # ---------------- Championship ----------------
    [
        C("Livingston", "LIV", (255, 210, 15), BLACK, "Almondvale Stadium", 9713, 55),
        C("Dunfermline Athletic", "DNF", BLACK, BLACK, "East End Park", 11480, 52, "stripes", WHITE),
        C("Partick Thistle", "PAR", RED, BLACK, "Firhill Stadium", 10887, 52, "stripes", (255, 215, 0)),
        C("Raith Rovers", "RAI", NAVY, NAVY, "Stark's Park", 8867, 51),
        C("Inverness CT", "ICT", BLUE, BLUE, "Caledonian Stadium", 7512, 50, "stripes", RED),
        C("Ayr United", "AYR", WHITE, BLACK, "Somerset Park", 10185, 50),
        C("Greenock Morton", "MOR", BLUE, WHITE, "Cappielow Park", 11589, 49, "hoops", WHITE),
        C("Queen's Park", "QPK", BLACK, WHITE, "Lesser Hampden", 990, 49, "hoops", WHITE),
        C("Arbroath", "ARB", (128, 0, 0), WHITE, "Gayfield Park", 6056, 47),
        C("Stenhousemuir", "STE", (100, 4, 20), WHITE, "Ochilview Park", 3746, 47),
    ],
    # ---------------- League One ----------------
    [
        C("Ross County", "ROS", NAVY, WHITE, "Victoria Park", 6541, 46),
        C("Airdrieonians", "AIR", WHITE, WHITE, "Excelsior Stadium", 10101, 45),
        C("Hamilton Academical", "HAM", RED, WHITE, "New Douglas Park", 6018, 44, "hoops", WHITE),
        C("Queen of the South", "QOS", BLUE, WHITE, "Palmerston Park", 8690, 43),
        C("Cove Rangers", "COV", BLUE, BLUE, "Balmoral Stadium", 2602, 43),
        C("Alloa Athletic", "ALL", (255, 165, 0), BLACK, "Recreation Park", 3100, 42, "hoops", BLACK),
        C("Montrose", "MON", BLUE, BLUE, "Links Park", 4936, 41),
        C("Peterhead", "PET", BLUE, BLUE, "Balmoor Stadium", 3150, 41),
        C("East Fife", "EFI", (242, 188, 0), BLACK, "Bayview Stadium", 1980, 40, "stripes", BLACK),
        C("East Kilbride", "EKB", (218, 165, 32), NAVY, "K-Park Training Academy", 700, 40),
    ],
    # ---------------- League Two ----------------
    [
        C("Kelty Hearts", "KEL", (96, 0, 32), (96, 0, 32), "New Central Park", 2181, 38),
        C("Annan Athletic", "ANN", (253, 212, 6), BLACK, "Galabank", 2504, 37, "stripes", BLACK),
        C("Dumbarton", "DUM", (253, 200, 20), BLACK, "The Rock", 2020, 37),
        C("Stirling Albion", "STA", RED, RED, "Forthbank Stadium", 3808, 37),
        C("Clyde", "CLY", WHITE, BLACK, "New Douglas Park", 6018, 36),
        C(
            "Forfar Athletic",
            "FOR",
            (120, 196, 255),
            (25, 45, 84),
            "Station Park",
            6777,
            36,
            "stripes",
            (25, 45, 84),
        ),
        C("Elgin City", "ELG", BLACK, BLACK, "Borough Briggs", 4520, 35, "stripes", WHITE),
        C("Stranraer", "STR", BLUE, WHITE, "Stair Park", 4178, 35),
        C("Edinburgh City", "EDC", WHITE, BLACK, "Meadowbank Stadium", 1280, 35),
        C("The Spartans", "SPA", WHITE, RED, "Ainslie Park", 3612, 34),
    ],
]

# Highland League (HL) and Lowland League (LL) clubs who can win the pyramid play-off
# and challenge League Two's bottom club. Squads for these clubs are generated.
NON_LEAGUE = "Highland/Lowland League"
PYRAMID_CLUBS = [
    ("HL", C("Brechin City", "BRE", RED, WHITE, "Glebe Park", 4083, 33)),
    ("HL", C("Buckie Thistle", "BUC", (0, 120, 60), WHITE, "Victoria Park", 5400, 31, "hoops", WHITE)),
    ("HL", C("Brora Rangers", "BRO", RED, WHITE, "Dudgeon Park", 4000, 30)),
    ("HL", C("Fraserburgh", "FRA", BLACK, BLACK, "Bellslea Park", 1800, 30, "stripes", WHITE)),
    ("LL", C("Bonnyrigg Rose", "BON", (180, 20, 30), WHITE, "New Dundas Park", 2200, 32)),
    ("LL", C("Linlithgow Rose", "LIN", (128, 0, 32), WHITE, "Prestonfield", 2264, 30)),
    ("LL", C("East Stirlingshire", "EST", BLACK, BLACK, "Falkirk Stadium", 7937, 29, "hoops", WHITE)),
]


def division_name(div: int, full: bool = True) -> str:
    if 0 <= div < len(DIVISIONS):
        return DIVISION_FULL[div] if full else DIVISIONS[div]
    return NON_LEAGUE if full else "non-league"


# Money (all in pounds)
TICKET_PRICE = [30, 20, 16, 14]
WEEKLY_INCOME = [90_000, 16_000, 9_000, 6_000]  # TV / sponsorship per week
SEASON_PRIZE_TOP = [3_000_000, 400_000, 150_000, 80_000]  # champions' prize money
LOAN_LIMIT = [2_000_000, 500_000, 250_000, 150_000]
OVERDRAFT_LIMIT = [2_500_000, 600_000, 300_000, 200_000]
CUP_PRIZE = [10_000, 20_000, 40_000, 90_000, 200_000, 500_000]
LOAN_WEEKLY_INTEREST = 0.005

CUP_NAME = "Scottish Cup"
CUP_ROUNDS = [
    "First Round",
    "Second Round",
    "Third Round",
    "Quarter-Final",
    "Semi-Final",
    "Final",
]
# Cup round N is played after this many league weeks
CUP_AFTER_LEAGUE_WEEK = {4: 0, 10: 1, 16: 2, 22: 3, 28: 4, 33: 5}
