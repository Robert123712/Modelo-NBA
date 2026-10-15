"""Motor 4: los cuatro factores de Dean Oliver.

Un partido se gana con cuatro cosas, en este orden de peso: tirar bien (eFG%),
no perder el balon (TOV%), recuperar tus fallos (ORB%) y llegar a la linea
(FT/FGA). Este motor sigue esos cuatro numeros por equipo, en ataque y en lo
que permite en defensa, y los convierte en puntos por posesion.

Lo que lo hace distinto de los otros tres es que trata cada factor segun su
ruido. El tiro (sobre todo de tres) es en buena parte suerte de corto plazo y
se regresa mas a la media; perdidas y rebote son habitos estables. Por eso cada
uno tiene su propia memoria y su propia regresion: un equipo que metio 45% de
tres dos semanas no se proyecta como si fuera a seguir asi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FACTORES = ["efg", "tov", "orb", "ftr"]


@dataclass
class ParametrosFactores:
    # Vida media en partidos de cada factor, y cuanto se regresa a la liga
    # (0 = nada, 1 = todo). El tiro es el mas ruidoso.
    vida_media: dict[str, float] = field(
        default_factory=lambda: {"efg": 25.0, "tov": 15.0, "orb": 15.0, "ftr": 20.0, "pace": 10.0}
    )
    regresion: dict[str, float] = field(
        default_factory=lambda: {"efg": 0.30, "tov": 0.10, "orb": 0.10, "ftr": 0.15, "pace": 0.0}
    )


def tabla_equipos(partidos: pd.DataFrame, jugadores: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo y partido con sus cuatro factores de ataque y defensa.

    Se suman los box de jugadores: asi la misma cuenta sirve para hoopR y para
    los partidos que se bajan de ESPN.
    """
    cols = {
        "points": "pts", "field_goals_made": "fgm", "field_goals_attempted": "fga",
        "three_point_field_goals_made": "tpm", "free_throws_made": "ftm",
        "free_throws_attempted": "fta", "offensive_rebounds": "oreb",
        "defensive_rebounds": "dreb", "turnovers": "tov",
    }
    t = jugadores.groupby(["game_id", "team_id"])[list(cols)].sum().rename(columns=cols).reset_index()
    rival = t.rename(columns={c: f"r_{c}" for c in cols.values()}).rename(columns={"team_id": "rival_id"})
    t = t.merge(rival, on="game_id")
    t = t[t.team_id != t.rival_id]
    info = partidos.set_index("game_id")[["fecha", "season", "posesiones", "minutos_juego", "home_id", "neutral"]]
    t = t.join(info, on="game_id", how="inner")
    pos = t.posesiones.clip(lower=1)

    def factores(pre):
        fga = t[f"{pre}fga"].clip(lower=1)
        return {
            "efg": (t[f"{pre}fgm"] + 0.5 * t[f"{pre}tpm"]) / fga,
            "tov": t[f"{pre}tov"] / pos,
            "orb": t[f"{pre}oreb"] / (t[f"{pre}oreb"] + t[("r_" if pre == "" else "")+"dreb"]).clip(lower=1),
            "ftr": t[f"{pre}ftm"] / fga,
        }

    of = factores("")
    de = factores("r_")
    for f in FACTORES:
        t[f"of_{f}"] = of[f]
        t[f"de_{f}"] = de[f]
    t["ortg"] = 100 * t.pts / pos
    t["pace"] = 48 * t.posesiones / t.minutos_juego
    t["local"] = (t.team_id == t.home_id) & ~t.neutral
    return t.sort_values(["fecha", "game_id"]).reset_index(drop=True)


@dataclass
class MapeoFactores:
    """Regresion de ORtg contra los cuatro factores (es casi contabilidad)."""
    coef: np.ndarray
    localia: float  # en ORtg, por lado

    def ortg(self, factores: np.ndarray, signo_local: float) -> np.ndarray:
        X = np.column_stack([np.ones(len(factores)), factores])
        return X @ self.coef + signo_local * self.localia


def ajustar_mapeo(t: pd.DataFrame) -> MapeoFactores:
    X = np.column_stack([np.ones(len(t))] + [t[f"of_{f}"].values for f in FACTORES])
    coef = np.linalg.lstsq(X, t.ortg.values, rcond=None)[0]
    no_neutral = t[~t.neutral]
    loc = (no_neutral[no_neutral.local].ortg.mean() - no_neutral[~no_neutral.local].ortg.mean()) / 2
    return MapeoFactores(coef=coef, localia=float(loc))


def _ewm(serie: pd.Series, vida: float) -> pd.Series:
    return serie.ewm(alpha=1 - 0.5 ** (1 / vida), adjust=True).mean()


def con_previos(t: pd.DataFrame, params: ParametrosFactores | None = None) -> pd.DataFrame:
    """Agrega el valor ANTES de cada partido de cada factor (ataque y defensa)."""
    params = params or ParametrosFactores()
    t = t.copy()
    g = t.groupby("team_id")
    for f in FACTORES + ["pace"]:
        vida = params.vida_media[f]
        columnas = [f"of_{f}", f"de_{f}"] if f != "pace" else ["pace"]
        for c in columnas:
            t[f"pre_{c}"] = g[c].transform(lambda s: _ewm(s, vida).shift(1))
        # Promedio de la liga en las ultimas ~2 semanas, tambien previo.
        liga = t[columnas[0]].rolling(200, min_periods=20).mean().shift(1)
        t[f"liga_{f}"] = liga
        r = params.regresion[f]
        for c in columnas:
            t[f"pre_{c}"] = (1 - r) * t[f"pre_{c}"] + r * t[f"liga_{f}"]
    return t


def esperado(fila_a: pd.Series, fila_b: pd.Series, liga: dict, mapeo: MapeoFactores,
             signo_local_a: float) -> float:
    """ORtg esperado del ataque A contra la defensa B."""
    x = np.array([[fila_a[f"of_{f}"] + fila_b[f"de_{f}"] - liga[f] for f in FACTORES]])
    return float(mapeo.ortg(x, signo_local_a)[0])


def predicciones(t: pd.DataFrame, partidos: pd.DataFrame, mapeo: MapeoFactores) -> pd.DataFrame:
    """Margen y total esperados (reglamento) de cada partido, con datos previos."""
    pre = t.set_index(["game_id", "team_id"])
    out = []
    for p in partidos.itertuples():
        try:
            c = pre.loc[(p.game_id, p.home_id)]
            v = pre.loc[(p.game_id, p.away_id)]
        except KeyError:
            continue
        valores = [c[f"pre_of_{f}"] for f in FACTORES] + [v[f"pre_of_{f}"] for f in FACTORES]
        if any(pd.isna(x) for x in valores):
            continue
        liga = {f: c[f"liga_{f}"] for f in FACTORES}
        a = {f"of_{f}": c[f"pre_of_{f}"] for f in FACTORES} | {f"de_{f}": c[f"pre_de_{f}"] for f in FACTORES}
        b = {f"of_{f}": v[f"pre_of_{f}"] for f in FACTORES} | {f"de_{f}": v[f"pre_de_{f}"] for f in FACTORES}
        s = 0.0 if p.neutral else 1.0
        ortg_c = esperado(a, b, liga, mapeo, s)
        ortg_v = esperado(b, a, liga, mapeo, -s)
        pace = c.pre_pace + v.pre_pace - c.liga_pace
        out.append((p.game_id, (ortg_c - ortg_v) * pace / 100, (ortg_c + ortg_v) * pace / 100))
    return pd.DataFrame(out, columns=["game_id", "margen_factores", "total_factores"])


def estado_actual(t: pd.DataFrame, params: ParametrosFactores | None = None) -> tuple[dict, dict]:
    """Ultimo valor de cada equipo (incluye su ultimo partido) y de la liga."""
    params = params or ParametrosFactores()
    equipos = {}
    for team, x in t.groupby("team_id"):
        d = {}
        for f in FACTORES + ["pace"]:
            for c in ([f"of_{f}", f"de_{f}"] if f != "pace" else ["pace"]):
                d[c] = float(_ewm(x[c], params.vida_media[f]).iloc[-1])
        equipos[int(team)] = d
    ult = t.tail(200)
    liga = {f: float(ult[f"of_{f}"].mean()) for f in FACTORES} | {"pace": float(ult.pace.mean())}
    for d in equipos.values():
        for f in FACTORES + ["pace"]:
            r = params.regresion[f]
            for c in ([f"of_{f}", f"de_{f}"] if f != "pace" else ["pace"]):
                d[c] = (1 - r) * d[c] + r * liga[f]
    return equipos, liga


def predecir(equipos: dict, liga: dict, mapeo: MapeoFactores, casa: int, visita: int,
             neutral: bool) -> tuple[float, float] | None:
    if casa not in equipos or visita not in equipos:
        return None
    a, b = equipos[casa], equipos[visita]
    s = 0.0 if neutral else 1.0
    ortg_c = esperado(a, b, liga, mapeo, s)
    ortg_v = esperado(b, a, liga, mapeo, -s)
    pace = a["pace"] + b["pace"] - liga["pace"]
    return ortg_c * pace / 100, ortg_v * pace / 100
