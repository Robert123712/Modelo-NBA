"""Apodo, ciudad en espanol y colores por equipo (abreviatura de ESPN)."""

EQUIPOS = {
    "ATL": ("Hawks", "Atlanta", "#E03A3E", "#C1D32F"),
    "BOS": ("Celtics", "Boston", "#007A33", "#BA9653"),
    "BKN": ("Nets", "Brooklyn", "#1D1D1D", "#8A8D8F"),
    "CHA": ("Hornets", "Charlotte", "#00788C", "#1D1160"),
    "CHI": ("Bulls", "Chicago", "#CE1141", "#1D1D1D"),
    "CLE": ("Cavaliers", "Cleveland", "#860038", "#FDBB30"),
    "DAL": ("Mavericks", "Dallas", "#00538C", "#002B5E"),
    "DEN": ("Nuggets", "Denver", "#0E2240", "#FEC524"),
    "DET": ("Pistons", "Detroit", "#C8102E", "#1D42BA"),
    "GS": ("Warriors", "Golden State", "#1D428A", "#FFC72C"),
    "HOU": ("Rockets", "Houston", "#CE1141", "#1D1D1D"),
    "IND": ("Pacers", "Indiana", "#002D62", "#FDBB30"),
    "LAC": ("Clippers", "Los Ángeles", "#C8102E", "#1D428A"),
    "LAL": ("Lakers", "Los Ángeles", "#552583", "#FDB927"),
    "MEM": ("Grizzlies", "Memphis", "#5D76A9", "#12173F"),
    "MIA": ("Heat", "Miami", "#98002E", "#F9A01B"),
    "MIL": ("Bucks", "Milwaukee", "#00471B", "#B8A97A"),
    "MIN": ("Timberwolves", "Minnesota", "#0C2340", "#78BE20"),
    "NO": ("Pelicans", "Nueva Orleans", "#0C2340", "#C8102E"),
    "NY": ("Knicks", "Nueva York", "#006BB6", "#F58426"),
    "OKC": ("Thunder", "Oklahoma City", "#007AC1", "#EF3B24"),
    "ORL": ("Magic", "Orlando", "#0077C0", "#1D1D1D"),
    "PHI": ("Sixers", "Filadelfia", "#006BB6", "#ED174C"),
    "PHX": ("Suns", "Phoenix", "#1D1160", "#E56020"),
    "POR": ("Trail Blazers", "Portland", "#E03A3E", "#1D1D1D"),
    "SAC": ("Kings", "Sacramento", "#5A2D81", "#63727A"),
    "SA": ("Spurs", "San Antonio", "#1D1D1D", "#8A8D8F"),
    "TOR": ("Raptors", "Toronto", "#CE1141", "#1D1D1D"),
    "UTAH": ("Jazz", "Utah", "#002B5C", "#F9A01B"),
    "WSH": ("Wizards", "Washington", "#002B5C", "#E31837"),
}


# NFL, con la abreviatura de ESPN. Dos colores: si el primero se parece
# demasiado al del rival, la plantilla puede usar el segundo.
NFL = {
    "ARI": ("Cardinals", "Arizona", "#97233F", "#1D1D1D"),
    "ATL": ("Falcons", "Atlanta", "#A71930", "#1D1D1D"),
    "BAL": ("Ravens", "Baltimore", "#241773", "#9E7C0C"),
    "BUF": ("Bills", "Buffalo", "#00338D", "#C60C30"),
    "CAR": ("Panthers", "Carolina", "#0085CA", "#1D1D1D"),
    "CHI": ("Bears", "Chicago", "#0B162A", "#C83803"),
    "CIN": ("Bengals", "Cincinnati", "#FB4F14", "#1D1D1D"),
    "CLE": ("Browns", "Cleveland", "#311D00", "#FF3C00"),
    "DAL": ("Cowboys", "Dallas", "#003594", "#869397"),
    "DEN": ("Broncos", "Denver", "#FB4F14", "#002244"),
    "DET": ("Lions", "Detroit", "#0076B6", "#8A8D8F"),
    "GB": ("Packers", "Green Bay", "#203731", "#FFB612"),
    "HOU": ("Texans", "Houston", "#03202F", "#A71930"),
    "IND": ("Colts", "Indianápolis", "#002C5F", "#8A8D8F"),
    "JAX": ("Jaguars", "Jacksonville", "#006778", "#9F792C"),
    "KC": ("Chiefs", "Kansas City", "#E31837", "#FFB81C"),
    "LV": ("Raiders", "Las Vegas", "#1D1D1D", "#8A8D8F"),
    "LAC": ("Chargers", "Los Ángeles", "#0080C6", "#FFC20E"),
    "LAR": ("Rams", "Los Ángeles", "#003594", "#FFA300"),
    "MIA": ("Dolphins", "Miami", "#008E97", "#FC4C02"),
    "MIN": ("Vikings", "Minnesota", "#4F2683", "#FFC62F"),
    "NE": ("Patriots", "Nueva Inglaterra", "#002244", "#C60C30"),
    "NO": ("Saints", "Nueva Orleans", "#1D1D1D", "#9F8958"),
    "NYG": ("Giants", "Nueva York", "#0B2265", "#A71930"),
    "NYJ": ("Jets", "Nueva York", "#125740", "#1D1D1D"),
    "PHI": ("Eagles", "Filadelfia", "#004C54", "#8A8D8F"),
    "PIT": ("Steelers", "Pittsburgh", "#1D1D1D", "#FFB612"),
    "SF": ("49ers", "San Francisco", "#AA0000", "#B3995D"),
    "SEA": ("Seahawks", "Seattle", "#002244", "#69BE28"),
    "TB": ("Buccaneers", "Tampa Bay", "#D50A0A", "#34302B"),
    "TEN": ("Titans", "Tennessee", "#0C2340", "#4B92DB"),
    "WSH": ("Commanders", "Washington", "#5A1414", "#FFB612"),
}
# nflverse escribe algunas distinto que ESPN.
ALIAS_NFL = {"WAS": "WSH", "LA": "LAR", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR"}


def equipo(abbr: str, liga: str = "nba") -> dict:
    if liga == "nfl":
        abbr = ALIAS_NFL.get(abbr.upper(), abbr.upper())
        apodo, ciudad, c1, c2 = NFL[abbr]
    else:
        apodo, ciudad, c1, c2 = EQUIPOS[abbr]
    return {"abbr": abbr, "apodo": apodo, "ciudad": ciudad, "color": c1, "color2": c2}
