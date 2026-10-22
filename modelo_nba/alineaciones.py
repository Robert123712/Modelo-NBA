"""Alineaciones titulares del dia, de la NBA.

`stats.nba.com/js/data/leaders/00_daily_lineups_AAAAMMDD.json` trae los cinco
titulares de cada equipo: "Expected" desde la manana y "Confirmed" cuando el
equipo la entrega (unos 30 minutos antes). A diferencia del resto de
stats.nba.com, esta ruta si responde desde GitHub Actions.

Saber quien arranca hoy, en vez de quien arranco el partido pasado, baja el
error de minutos de 4.85 a 4.69 en 2025-26 (docs/MINUTOS.md).
"""

from __future__ import annotations

import datetime as dt

import requests

from .datos import clave_nombre

URL = "https://stats.nba.com/js/data/leaders/00_daily_lineups_{:%Y%m%d}.json"
AGENTE = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"}


def parse(data: dict) -> dict[str, dict]:
    """Por equipo (abreviatura NBA): {"estado": "Confirmed"|"Expected",
    "titulares": {clave_nombre, ...}, "hora": timestamp}.

    En "Confirmed" la NBA lista a todo el roster y solo los titulares traen
    posicion; en "Expected" solo vienen los cinco.
    """
    out = {}
    for g in data.get("games", []):
        for lado in ("homeTeam", "awayTeam"):
            t = g.get(lado) or {}
            jug = t.get("players") or []
            titulares = {clave_nombre(p.get("playerName", "")) for p in jug if p.get("position")}
            if len(titulares) != 5:
                continue
            estados = {p.get("lineupStatus") for p in jug if p.get("position")}
            out[t.get("teamAbbreviation")] = {
                "estado": "Confirmed" if estados == {"Confirmed"} else "Expected",
                "titulares": titulares,
                "hora": max((p.get("timestamp") or "" for p in jug), default=None),
            }
    return out


def del_dia(fecha: dt.date, sesion: requests.Session | None = None) -> dict[str, dict]:
    s = sesion or requests.Session()
    r = s.get(URL.format(fecha), headers=AGENTE, timeout=30)
    r.raise_for_status()
    return parse(r.json())


def del_equipo(alineaciones: dict[str, dict], roster: list[dict]) -> dict | None:
    """La alineacion que corresponde a un roster de ESPN: la del equipo con
    los cinco titulares en ese roster (las abreviaturas de ESPN y la NBA no
    siempre coinciden: GS/GSW, NY/NYK...). Devuelve {"estado", "titulares":
    {athlete_id, ...}, "hora"} o None."""
    por_clave = {clave_nombre(r["nombre"]): r["athlete_id"] for r in roster}
    mejor = max(alineaciones.values(), key=lambda eq: len(eq["titulares"] & set(por_clave)), default=None)
    # Con 4 de 5 basta: un nombre escrito distinto no tira la alineacion.
    if mejor is None or len(mejor["titulares"] & set(por_clave)) < 4:
        return None
    return {"estado": mejor["estado"], "hora": mejor["hora"],
            "titulares": {por_clave[k] for k in mejor["titulares"] if k in por_clave}}
