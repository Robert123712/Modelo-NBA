"""Historia que usa la corrida diaria: hoopR para lo viejo, ESPN para lo reciente.

hoopR republica todos los dias a las 07:00 UTC durante la temporada. Para no
depender de que su corrida haya salido bien, los partidos terminados que todavia
no esten en hoopR se bajan de ESPN y se guardan en `data/box/`, que viaja en el
repo. Asi cada corrida ve todo lo jugado hasta ayer, venga de donde venga.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

from . import espn, historico

DIR_BOX = Path("data/box")
TEMPORADAS_ATRAS = 3


def _cargar_tolerante(temporadas: list[int], refrescar_ultima: bool):
    """Como historico.cargar, pero una temporada sin publicar no es error.

    Antes del primer partido hoopR no tiene player_box de la temporada nueva.
    """
    partidos, jugadores = [], []
    for s in temporadas:
        try:
            p, j = historico.cargar([s], refrescar_ultima=refrescar_ultima and s == max(temporadas))
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                continue
            raise
        partidos.append(p)
        jugadores.append(j)
    return partidos, jugadores


def _ruta(temporada: int, que: str) -> Path:
    return DIR_BOX / f"{que}_{temporada}.parquet"


def complemento(temporada: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    p, j = _ruta(temporada, "partidos"), _ruta(temporada, "jugadores")
    if p.exists() and j.exists():
        return pd.read_parquet(p), pd.read_parquet(j)
    return pd.DataFrame(), pd.DataFrame()


def completar_con_espn(
    temporada: int,
    conocidos: set[int],
    desde: dt.date,
    hasta: dt.date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Baja de ESPN los terminados entre `desde` y `hasta` que no esten en `conocidos`."""
    prev_p, prev_j = complemento(temporada)
    ya = conocidos | set(prev_p.game_id) if len(prev_p) else set(conocidos)
    nuevos_p, nuevos_j = [], []
    dia = desde
    while dia <= hasta:
        for juego in espn.scoreboard(dia):
            if (
                juego["terminado"]
                and juego["season"] == temporada
                and juego["season_type"] in historico.TIPOS_VALIDOS
                and juego["game_id"] not in ya
            ):
                partido, filas = espn.box_desde_summary(espn.summary(juego["game_id"]))
                nuevos_p.append(partido)
                nuevos_j.extend(filas)
                ya.add(juego["game_id"])
        dia += dt.timedelta(days=1)
    if nuevos_p:
        p = pd.DataFrame(nuevos_p)
        p["dia"] = p.fecha.dt.tz_convert("America/New_York").dt.date
        j = pd.DataFrame(nuevos_j)
        p = pd.concat([prev_p, p], ignore_index=True) if len(prev_p) else p
        j = pd.concat([prev_j, j], ignore_index=True) if len(prev_j) else j
        DIR_BOX.mkdir(parents=True, exist_ok=True)
        p.drop(columns=["dia"]).to_parquet(_ruta(temporada, "partidos"), index=False)
        j.to_parquet(_ruta(temporada, "jugadores"), index=False)
        return p, j
    return complemento(temporada)


def historia(temporada: int, hoy: dt.date, inicio_temporada: dt.date | None, usar_espn: bool = True):
    """Partidos y jugadores de las ultimas temporadas, hasta ayer."""
    temporadas = list(range(temporada - TEMPORADAS_ATRAS, temporada + 1))
    partidos, jugadores = _cargar_tolerante(temporadas, refrescar_ultima=True)
    conocidos = set(pd.concat(partidos).game_id) if partidos else set()

    if usar_espn and inicio_temporada and inicio_temporada < hoy:
        actuales = [p for p in partidos if (p.season == temporada).any()]
        ultimo = max(p[p.season == temporada].dia.max() for p in actuales) if actuales else None
        # Se revisa desde dos dias antes del ultimo que trae hoopR: un partido
        # que termino despues de su corrida puede faltar aunque el dia este.
        desde = max(inicio_temporada, ultimo - dt.timedelta(days=2)) if ultimo else inicio_temporada
        cp, cj = completar_con_espn(temporada, conocidos, desde, hoy - dt.timedelta(days=1))
    else:
        cp, cj = complemento(temporada)
    if len(cp):
        cp = cp[~cp.game_id.isin(conocidos)].copy()
        cp["fecha"] = pd.to_datetime(cp.fecha, utc=True)
        cp["dia"] = cp.fecha.dt.tz_convert("America/New_York").dt.date
        cj = cj[cj.game_id.isin(cp.game_id)].copy()
        cj["minutes"] = cj.minutes.fillna(0.0)
        cj["reason"] = cj.reason.fillna("")
        partidos.append(cp)
        jugadores.append(cj[historico.COLUMNAS_JUGADOR])

    p = pd.concat(partidos, ignore_index=True).sort_values(["fecha", "game_id"]).reset_index(drop=True)
    j = pd.concat(jugadores, ignore_index=True)
    return p, j


def calendario(temporada: int) -> pd.DataFrame:
    """Calendario completo de la temporada (para fecha de arranque y b2b)."""
    sc = pd.read_parquet(historico.ruta_local(f"schedules/parquet/nba_schedule_{temporada}.parquet", True))
    sc["fecha"] = pd.to_datetime(sc.date, utc=True)
    sc["dia"] = sc.fecha.dt.tz_convert("America/New_York").dt.date
    return sc


def novatos(temporada: int) -> pd.DataFrame:
    """Draft que entra en esta temporada (el de junio anterior), por nombre.

    Los id del draft de hoopR no son los de ESPN, asi que se cruza por nombre
    normalizado.
    """
    try:
        d = pd.read_parquet(historico.ruta_local(f"draft/parquet/draft_{temporada - 1}.parquet"))
    except requests.HTTPError:
        return pd.DataFrame(columns=["clave", "overall_pick"])
    return pd.DataFrame({
        "clave": d.athlete_display_name.map(clave_nombre),
        "overall_pick": d.overall_pick.astype(int),
    })


def clave_nombre(nombre: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(nombre)).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.lower() if ch.isalnum())


def minutos_novato(pick: int | None) -> float:
    """Minutos de arranque segun el turno, medidos en la clase de 2025."""
    if pick is None:
        return 6.0
    if pick <= 5:
        return 27.0
    if pick <= 14:
        return 15.0
    if pick <= 30:
        return 9.0
    return 6.0
