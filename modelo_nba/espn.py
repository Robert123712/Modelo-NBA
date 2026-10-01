"""Cliente de la API publica de ESPN: slate, box scores, rosters y bajas.

Todo lo que entra se valida al parsear y falla en voz alta: un campo que cambio
de nombre debe tumbar la corrida, no producir un slate vacio que se publique
como "hoy no hay partidos".
"""

from __future__ import annotations

import datetime as dt
import time

import pandas as pd
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
TIMEOUT = 30

# Probabilidad de jugar segun el estado en el roster de ESPN. ESPN solo usa
# "Out" y "Day-To-Day"; el segundo mezcla probables y dudosos, asi que se toma
# un punto medio y se avisa en el partido. El reporte oficial de la NBA
# (Questionable / Doubtful / Probable) lo afinara.
PROB_JUEGA = {
    "out": 0.0,
    "doubtful": 0.25,
    "questionable": 0.5,
    "day-to-day": 0.6,
    "probable": 0.9,
    "active": 1.0,
}


class ErrorESPN(RuntimeError):
    pass


def _get(url: str, params: dict | None = None, intentos: int = 3) -> dict:
    ultimo = None
    for k in range(intentos):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            ultimo = f"HTTP {r.status_code}"
        except requests.RequestException as e:  # red intermitente
            ultimo = str(e)
        time.sleep(2 ** k)
    raise ErrorESPN(f"{url}: {ultimo}")


# --- Slate -----------------------------------------------------------------


def parse_scoreboard(data: dict) -> list[dict]:
    if "events" not in data:
        raise ErrorESPN("scoreboard sin 'events'")
    juegos = []
    for ev in data["events"]:
        comp = ev["competitions"][0]
        lados = {c["homeAway"]: c for c in comp["competitors"]}
        if set(lados) != {"home", "away"}:
            raise ErrorESPN(f"evento {ev.get('id')} sin local y visita")
        estado = comp.get("status", ev.get("status", {}))["type"]
        juegos.append({
            "game_id": int(ev["id"]),
            "starts_at": ev["date"],
            "season": int(ev["season"]["year"]),
            "season_type": int(ev["season"]["type"]),
            "neutral": bool(comp.get("neutralSite", False)),
            "estado": estado["state"],  # pre | in | post
            "terminado": bool(estado.get("completed", False)),
            **{
                f"{lado}_{campo}": valor
                for lado, c in lados.items()
                for campo, valor in (
                    ("id", int(c["team"]["id"])),
                    ("abbr", c["team"]["abbreviation"]),
                    ("nombre", c["team"]["displayName"]),
                )
            },
        })
    return juegos


def scoreboard(fecha: dt.date) -> list[dict]:
    return parse_scoreboard(
        _get(f"{BASE}/scoreboard", {"dates": fecha.strftime("%Y%m%d"), "limit": 100})
    )


# --- Box score de un partido terminado -------------------------------------

_MAPA_JUGADOR = {
    "minutes": "minutes",
    "points": "points",
    "offensiveRebounds": "offensive_rebounds",
    "defensiveRebounds": "defensive_rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
    "fouls": "fouls",
}
_PARES = {
    "fieldGoalsMade-fieldGoalsAttempted": ("field_goals_made", "field_goals_attempted"),
    "threePointFieldGoalsMade-threePointFieldGoalsAttempted": (
        "three_point_field_goals_made", "three_point_field_goals_attempted"),
    "freeThrowsMade-freeThrowsAttempted": ("free_throws_made", "free_throws_attempted"),
}


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def box_desde_summary(data: dict) -> tuple[dict, list[dict]]:
    """Partido y filas de jugador con las mismas columnas que hoopR.

    Las columnas del box se leen por su clave (`keys`), no por posicion: ESPN
    cambia el orden entre temporadas.
    """
    comp = data["header"]["competitions"][0]
    gid = int(comp["id"])
    lados = {c["homeAway"]: c for c in comp["competitors"]}
    lineas = {
        lado: [_num(l.get("value", l.get("displayValue"))) for l in c.get("linescores", [])]
        for lado, c in lados.items()
    }
    periodos = max(4, len(lineas["home"]), len(lineas["away"]))

    def stat_equipo(team_id: str, nombre: str) -> str:
        for t in data["boxscore"]["teams"]:
            if str(t["team"]["id"]) == team_id:
                for s in t["statistics"]:
                    if s["name"] == nombre:
                        return s["displayValue"]
        raise ErrorESPN(f"{gid}: falta {nombre} del equipo {team_id}")

    pos = []
    for lado in ("home", "away"):
        tid = str(lados[lado]["team"]["id"])
        fga = _num(stat_equipo(tid, "fieldGoalsMade-fieldGoalsAttempted").split("-")[1])
        fta = _num(stat_equipo(tid, "freeThrowsMade-freeThrowsAttempted").split("-")[1])
        oreb = _num(stat_equipo(tid, "offensiveRebounds"))
        tov = _num(stat_equipo(tid, "totalTurnovers"))
        pos.append(fga + 0.44 * fta - oreb + tov)

    season = data["header"]["season"]
    partido = {
        "game_id": gid,
        "season": int(season["year"]),
        "season_type": int(season["type"]),
        "fecha": pd.Timestamp(comp["date"]).tz_convert("UTC") if pd.Timestamp(comp["date"]).tzinfo else pd.Timestamp(comp["date"], tz="UTC"),
        "home_id": int(lados["home"]["team"]["id"]),
        "away_id": int(lados["away"]["team"]["id"]),
        "home_abbr": lados["home"]["team"]["abbreviation"],
        "away_abbr": lados["away"]["team"]["abbreviation"],
        "neutral": bool(comp.get("neutralSite", False)),
        "home_pts": _num(lados["home"]["score"]),
        "away_pts": _num(lados["away"]["score"]),
        "home_1h": sum(lineas["home"][:2]),
        "away_1h": sum(lineas["away"][:2]),
        "home_reg": sum(lineas["home"][:4]),
        "away_reg": sum(lineas["away"][:4]),
        "periodos": periodos,
        "posesiones": sum(pos) / 2,
        "minutos_juego": 48 + 5 * (periodos - 4),
    }

    filas = []
    for bloque in data["boxscore"]["players"]:
        tid = int(bloque["team"]["id"])
        st = bloque["statistics"][0]
        claves = st["keys"]
        for a in st["athletes"]:
            fila = {
                "game_id": gid,
                "team_id": tid,
                "athlete_id": int(a["athlete"]["id"]),
                "athlete_display_name": a["athlete"]["displayName"],
                "starter": bool(a.get("starter", False)),
                "did_not_play": bool(a.get("didNotPlay", False)) or not a.get("stats"),
                "reason": a.get("reason") or "",
            }
            for col in list(_MAPA_JUGADOR.values()) + [c for par in _PARES.values() for c in par]:
                fila[col] = 0.0
            for clave, valor in zip(claves, a.get("stats") or []):
                if clave in _MAPA_JUGADOR:
                    fila[_MAPA_JUGADOR[clave]] = _num(valor)
                elif clave in _PARES and "-" in str(valor):
                    hechos, intentos = str(valor).split("-", 1)
                    fila[_PARES[clave][0]] = _num(hechos)
                    fila[_PARES[clave][1]] = _num(intentos)
            filas.append(fila)
    if not filas:
        raise ErrorESPN(f"{gid}: box score sin jugadores")
    return partido, filas


def summary(game_id: int) -> dict:
    return _get(f"{BASE}/summary", {"event": game_id})


# --- Roster y bajas --------------------------------------------------------


def parse_roster(data: dict) -> list[dict]:
    """Jugadores del roster con su probabilidad de jugar."""
    if "athletes" not in data:
        raise ErrorESPN("roster sin 'athletes'")
    atletas = data["athletes"]
    # Algunas variantes del endpoint agrupan por posicion: [{items: [...]}].
    if atletas and "items" in atletas[0]:
        atletas = [x for grupo in atletas for x in grupo["items"]]
    out = []
    for a in atletas:
        estado = "active"
        for i in a.get("injuries") or []:
            estado = str(i.get("status", "active")).lower()
        out.append({
            "athlete_id": int(a["id"]),
            "nombre": a.get("displayName") or a.get("fullName", ""),
            "estado": estado,
            "prob_juega": PROB_JUEGA.get(estado, 0.5),
            "estado_conocido": estado in PROB_JUEGA,
        })
    return out


def roster(team_id: int) -> list[dict]:
    return parse_roster(_get(f"{BASE}/teams/{team_id}/roster"))
