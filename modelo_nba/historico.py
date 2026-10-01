"""Carga del historico desde hoopR-nba-data (sportsdataverse).

hoopR publica en GitHub, por temporada, los box scores de ESPN ya tabulados y
una tabla de lineas de cierre de consenso. Es la fuente del entrenamiento y del
backtest: llega por raw.githubusercontent.com, que se alcanza tanto desde
Actions como desde un entorno sin acceso a ESPN.

La temporada se nombra como la nombra ESPN: 2026 es la 2025-26.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = "https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data/main/nba"
CACHE = Path(os.environ.get("MODELO_NBA_CACHE", "cache"))

# Temporada regular, playoffs y play-in. Se excluyen pretemporada y All-Star:
# no se juegan para ganar con la rotacion real.
TIPOS_VALIDOS = (2, 3, 5)

MINUTOS_REGLAMENTO = 48
MINUTOS_OT = 5

_VALOR = re.compile(r"'value':\s*(-?\d+(?:\.\d+)?)")


def ruta_local(relativa: str, refrescar: bool = False) -> Path:
    """Devuelve el parquet en disco, bajandolo si no esta.

    `HOOPR_LOCAL` apunta a un clon de hoopR-nba-data y evita la descarga.
    """
    clon = os.environ.get("HOOPR_LOCAL")
    if clon:
        p = Path(clon) / "nba" / relativa
        if p.exists():
            return p
    destino = CACHE / relativa
    if destino.exists() and not refrescar:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(f"{BASE}/{relativa}", timeout=60)
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def _parquet(relativa: str, refrescar: bool = False) -> pd.DataFrame:
    return pd.read_parquet(ruta_local(relativa, refrescar))


def parse_linescores(texto) -> list[float]:
    """Puntos por periodo, en orden.

    hoopR guarda la columna como el repr de una lista de dicts, y el formato
    cambio entre temporadas (con y sin `period`). Lo unico estable es `'value'`,
    en orden de periodo.
    """
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return []
    return [float(v) for v in _VALOR.findall(str(texto))]


def partidos_de(schedule: pd.DataFrame, team_box: pd.DataFrame) -> pd.DataFrame:
    """Una fila por partido terminado, con posesiones y primera mitad."""
    sc = schedule[
        schedule.season_type.isin(TIPOS_VALIDOS)
        & (schedule.status_type_name == "STATUS_FINAL")
    ].copy()

    lh = sc.home_linescores.map(parse_linescores)
    la = sc.away_linescores.map(parse_linescores)
    sc["periodos"] = [max(len(a), len(b)) for a, b in zip(lh, la)]
    sc["home_1h"] = [sum(x[:2]) if len(x) >= 2 else np.nan for x in lh]
    sc["away_1h"] = [sum(x[:2]) if len(x) >= 2 else np.nan for x in la]
    sc["home_reg"] = [sum(x[:4]) if len(x) >= 4 else np.nan for x in lh]
    sc["away_reg"] = [sum(x[:4]) if len(x) >= 4 else np.nan for x in la]
    # Sin cuartos no se sabe si hubo OT; se asume reglamento y se marca.
    sc["periodos"] = sc.periodos.where(sc.periodos >= 4, 4)

    tb = team_box.copy()
    tb["pos_est"] = (
        tb.field_goals_attempted
        + 0.44 * tb.free_throws_attempted
        - tb.offensive_rebounds
        + tb.total_turnovers
    )
    pos = tb.groupby("game_id").pos_est.mean().rename("posesiones")

    out = pd.DataFrame(
        {
            "game_id": sc.game_id.astype("int64"),
            "season": sc.season.astype(int),
            "season_type": sc.season_type.astype(int),
            "fecha": pd.to_datetime(sc.date, utc=True),
            "home_id": sc.home_id.astype(int),
            "away_id": sc.away_id.astype(int),
            "home_abbr": sc.home_abbreviation,
            "away_abbr": sc.away_abbreviation,
            "neutral": sc.neutral_site.fillna(False).astype(bool),
            "home_pts": pd.to_numeric(sc.home_score, errors="coerce"),
            "away_pts": pd.to_numeric(sc.away_score, errors="coerce"),
            "home_1h": sc.home_1h,
            "away_1h": sc.away_1h,
            "home_reg": sc.home_reg,
            "away_reg": sc.away_reg,
            "periodos": sc.periodos.astype(int),
        }
    )
    out = out.merge(pos, left_on="game_id", right_index=True, how="inner")
    out = out.dropna(subset=["home_pts", "away_pts", "posesiones"])
    out["minutos_juego"] = MINUTOS_REGLAMENTO + MINUTOS_OT * (out.periodos - 4)
    # Fecha de calendario en el Este: es la que define "el slate de hoy" y los
    # back-to-back. Un partido a las 22:30 ET cae al dia siguiente en UTC.
    out["dia"] = out.fecha.dt.tz_convert("America/New_York").dt.date
    return out.sort_values(["fecha", "game_id"]).reset_index(drop=True)


COLUMNAS_JUGADOR = [
    "game_id", "team_id", "athlete_id", "athlete_display_name", "minutes",
    "starter", "did_not_play", "reason", "points", "field_goals_made",
    "field_goals_attempted", "three_point_field_goals_made",
    "three_point_field_goals_attempted", "free_throws_made",
    "free_throws_attempted", "offensive_rebounds", "defensive_rebounds",
    "assists", "steals", "blocks", "turnovers", "fouls",
]


def jugadores_de(player_box: pd.DataFrame, partidos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por jugador y partido, incluidos los que no jugaron.

    Se conservan los DNP: distinguir "no jugo por decision del coach" de "no
    estaba disponible" es lo que permite proyectar minutos sin contar la
    lesion como si fuera un rol.
    """
    pb = player_box[COLUMNAS_JUGADOR].copy()
    pb = pb[pb.game_id.isin(partidos.game_id)]
    pb = pb.dropna(subset=["athlete_id"])
    pb["athlete_id"] = pb.athlete_id.astype("int64")
    pb["game_id"] = pb.game_id.astype("int64")
    pb["team_id"] = pb.team_id.astype(int)
    pb["minutes"] = pb.minutes.fillna(0.0)
    stats = COLUMNAS_JUGADOR[8:]
    pb[stats] = pb[stats].fillna(0.0)
    pb["did_not_play"] = pb.did_not_play.fillna(pb.minutes <= 0).astype(bool)
    pb["reason"] = pb.reason.fillna("")
    return pb.reset_index(drop=True)


def cargar(temporadas: list[int], refrescar_ultima: bool = False):
    """Partidos y jugadores de las temporadas pedidas."""
    partidos, jugadores = [], []
    for i, s in enumerate(sorted(temporadas)):
        refrescar = refrescar_ultima and i == len(temporadas) - 1
        sc = _parquet(f"schedules/parquet/nba_schedule_{s}.parquet", refrescar)
        tb = _parquet(f"team_box/parquet/team_box_{s}.parquet", refrescar)
        pb = _parquet(f"player_box/parquet/player_box_{s}.parquet", refrescar)
        p = partidos_de(sc, tb)
        partidos.append(p)
        jugadores.append(jugadores_de(pb, p))
    return (
        pd.concat(partidos, ignore_index=True).sort_values(["fecha", "game_id"]).reset_index(drop=True),
        pd.concat(jugadores, ignore_index=True),
    )


def lineas_de_cierre() -> pd.DataFrame:
    """Cierre de consenso (mediana entre casas, The Odds API) por partido ESPN.

    `linea_casa` usa el signo de Las Vegas: negativo cuando el local es favorito.
    Solo se usa para calificar; el modelo no lee momios.
    """
    c = _parquet("betting_lines/closing_lines_odds_api.parquet")
    return pd.DataFrame(
        {
            "game_id": c.game_id.astype("int64"),
            "linea_casa": c.home_point.astype(float),
            "total_cierre": c.over_under.astype(float),
            "casas": c.n_books,
        }
    ).drop_duplicates("game_id")
