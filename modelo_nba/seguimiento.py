"""Seguimiento de props: lo que dijo el modelo contra lo que hizo cada jugador.

La prediccion que se califica es la oficial (la ultima con 60 minutos de
anticipacion), que guarda por jugador la media y el rango 80% de cada
estadistica y su promedio de la temporada hasta ese dia. Cuando el partido ya
tiene box score se compara:

* **Error del modelo** contra **error del promedio de temporada**: si el
  modelo no le gana a un promedio simple, no aporta nada.
* **Dentro del rango 80%**: debe acercarse a 80%. Mucho menos es que el modelo
  se cree mas seguro de lo que es.
* **Sesgo**: si proyecta de mas o de menos en promedio.

Un jugador que no jugo no cuenta: el prop se anula.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# Nombre publicado -> columnas del box score que lo suman.
STATS = {
    "puntos": ("points",),
    "rebotes": ("reb",),
    "asistencias": ("assists",),
    "pra": ("points", "reb", "assists"),
    "puntos_rebotes": ("points", "reb"),
    "puntos_asistencias": ("points", "assists"),
}
BASE = {"puntos": "points", "rebotes": "reb", "asistencias": "assists"}
DIAS_SERIE = 30
POR_JUGADOR = 5


def compacto(props_juego: dict, prom: pd.DataFrame | None, infos: dict | None = None) -> list[dict]:
    """Lo que se guarda en la oficial de cada jugador: chico a proposito.

    `s`: estadistica -> [media, p10, p90]. `prom`: promedio de la temporada de
    puntos, rebotes y asistencias hasta ese dia (la vara a la que le debe ganar).
    `ctx` (de `infos`, el `info` de simular_props): lo que movio la proyeccion,
    para poder entrenar despues contra el resultado: minutos con el roster
    sano, factor del rival y de las bajas por estadistica, posicion y si estaba
    en duda.
    """
    out = []
    for lado in ("home", "away"):
        for x in props_juego.get(lado, []):
            a = x["athlete_id"]
            fila = {
                "a": a, "j": x["jugador"], "lado": lado, "min": x["minutos"],
                "s": {k: [round(x[k]["media"], 2), x[k]["p10"], x[k]["p90"]] for k in STATS},
            }
            info = (infos or {}).get(a)
            if info:
                fila["ctx"] = {
                    "min_sano": None if info.get("minutos_completo") is None else round(info["minutos_completo"], 1),
                    "rival": {k: round(v, 3) for k, v in info["rival"].items()},
                    "bajas": {k: round(v, 3) for k, v in info["bajas"].items()},
                    "grupo": info.get("grupo"),
                    "duda": bool(x.get("en_duda")),
                }
            if prom is not None and a in prom.index:
                base = {c: float(prom.at[a, ("temporada", c)]) for c in BASE.values()}
                if all(v == v for v in base.values()):
                    # Los combinados contra la suma de sus promedios.
                    fila["prom"] = {k: round(sum(base[c] for c in cols), 2) for k, cols in STATS.items()}
            out.append(fila)
    return out


def _box(jugadores: pd.DataFrame) -> pd.DataFrame:
    j = jugadores.copy()
    j["reb"] = j.offensive_rebounds + j.defensive_rebounds
    return j.drop_duplicates(["game_id", "athlete_id"]).set_index(["game_id", "athlete_id"])


def filas(dir_oficiales: Path, jugadores: pd.DataFrame, partidos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por jugador, estadistica y partido ya jugado."""
    box = _box(jugadores)
    jugados = set(partidos.game_id.astype(int))
    out = []
    for ruta in sorted(dir_oficiales.glob("*.json")):
        for gid, rec in json.loads(ruta.read_text()).items():
            if "props" not in rec or int(gid) not in jugados:
                continue
            p = rec["proyeccion"]
            equipos = {"home": p["home"].get("code"), "away": p["away"].get("code")}
            for x in rec["props"]:
                clave = (int(gid), int(x["a"]))
                if clave not in box.index:
                    continue
                b = box.loc[clave]
                if bool(b.did_not_play) or float(b.minutes) <= 0:
                    continue  # no jugo: el prop se anula
                rival = equipos["away" if x["lado"] == "home" else "home"]
                for stat, cols in STATS.items():
                    media, p10, p90 = x["s"][stat]
                    out.append({
                        "fecha": ruta.stem, "game_id": int(gid), "athlete_id": int(x["a"]),
                        "jugador": x["j"], "equipo": equipos[x["lado"]], "rival": rival,
                        "min_proy": x["min"], "min_real": float(b.minutes),
                        "stat": stat, "proy": media, "p10": p10, "p90": p90,
                        "real": float(sum(b[c] for c in cols)),
                        "prom": x.get("prom", {}).get(stat, np.nan),
                    })
    return pd.DataFrame(out)


def _resumen(d: pd.DataFrame) -> dict:
    con_prom = d.dropna(subset=["prom"])
    return {
        "n": int(len(d)),
        "error_modelo": round(float((d.proy - d.real).abs().mean()), 2),
        "error_promedio": round(float((con_prom.prom - con_prom.real).abs().mean()), 2) if len(con_prom) else None,
        "n_promedio": int(len(con_prom)),
        "sesgo": round(float((d.proy - d.real).mean()), 2),
        "en_rango80": round(float(((d.real >= d.p10) & (d.real <= d.p90)).mean()), 3),
    }


def calificar(dir_oficiales: Path, jugadores: pd.DataFrame, partidos: pd.DataFrame) -> dict:
    """El record de props que publica el modelo (data/props-record.json)."""
    d = filas(dir_oficiales, jugadores, partidos)
    if d.empty:
        return {"jugadores_partido": 0, "resumen": {}, "por_dia": [], "ultimo_dia": None, "por_jugador": {}}
    resumen = {s: _resumen(x) for s, x in d.groupby("stat", sort=False)}
    base = d[d.stat.isin(BASE)]
    por_dia = [
        {"fecha": f, "n": int(x.game_id.astype(str).add(x.athlete_id.astype(str)).nunique()),
         **{s: round(float((y.proy - y.real).abs().mean()), 2) for s, y in x.groupby("stat")}}
        for f, x in base.groupby("fecha")
    ][-DIAS_SERIE:]

    # El ultimo dia calificado, jugador por jugador.
    fecha = d.fecha.max()
    hoy = d[d.fecha == fecha]
    ultimo = []
    for (gid, a), x in hoy.groupby(["game_id", "athlete_id"], sort=False):
        r = x.iloc[0]
        ultimo.append({
            "jugador": r.jugador, "equipo": r.equipo, "rival": r.rival,
            "min": [round(r.min_proy, 1), r.min_real],
            **{s.stat: [s.proy, s.real, s.p10, s.p90] for s in x.itertuples()},
        })

    # Ultimos partidos de cada jugador, para verlo debajo de su nombre.
    por_jugador: dict[str, list] = {}
    for a, x in base.sort_values("fecha").groupby("athlete_id"):
        juegos = []
        for gid, y in list(x.groupby("game_id", sort=False))[-POR_JUGADOR:]:
            r = y.iloc[0]
            juegos.append({"fecha": r.fecha, "rival": r.rival,
                           **{s.stat: [s.proy, s.real] for s in y.itertuples()}})
        por_jugador[str(a)] = juegos
    return {
        "jugadores_partido": int(d.groupby(["game_id", "athlete_id"]).ngroups),
        "dias": int(d.fecha.nunique()),
        "resumen": resumen,
        "por_dia": por_dia,
        "ultimo_dia": {"fecha": fecha, "jugadores": ultimo},
        "por_jugador": por_jugador,
    }
