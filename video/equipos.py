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


def equipo(abbr: str) -> dict:
    apodo, ciudad, c1, c2 = EQUIPOS[abbr]
    return {"abbr": abbr, "apodo": apodo, "ciudad": ciudad, "color": c1, "color2": c2}
