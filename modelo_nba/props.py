"""Props de jugador: puntos, rebotes, asistencias y sus combinados.

Un prop es minutos por produccion. Los minutos ya los proyecta `minutos.py`
con las bajas del dia; aqui se agrega lo que cada jugador produce, y se simula
junto con el partido para que las dos cosas se muevan juntas:

* **Tasa por posesion en cancha**, con memoria reciente y encogida hacia la
  liga. Por posesion y no por minuto, para que el ritmo del partido entre solo.
* **Puntos amarrados al marcador del equipo.** Cada jugador se lleva su parte
  de los puntos que el simulador le da a su equipo en esa simulacion: si el
  equipo anota 130, sus jugadores anotan mas; los puntos de la rotacion no
  pueden contradecir al marcador.
* **Rebotes y asistencias ajustados por rival**: lo que cada defensa permite
  por posesion, respecto a la liga.
* **Paliza.** Por cada punto de margen arriba de 8, los titulares pierden
  minutos (medido: 32 en partido cerrado, 26 con 30+ de diferencia). Por eso
  el prop sale de simular el partido, no de un promedio.
* **Ruido.** Los puntos varian ~2.5 veces lo que daria un conteo simple
  (Poisson); rebotes y asistencias casi nada. Cada estadistica tiene su
  dispersion, y las tres de un jugador comparten sus minutos simulados, asi
  que los combinados (PRA, P+R, P+A) salen correlacionados, no sumados.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .minutos import no_disponible

STATS = ("points", "reb", "assists")
COMBOS = {"pra": ("points", "reb", "assists"), "pr": ("points", "reb"), "pa": ("points", "assists")}
ROTACION = 8


@dataclass
class ParametrosProps:
    vida_media_partidos: float = 60.0
    # Posesiones ficticias con la tasa de la liga: cuanto se encoge un jugador
    # con poca muestra.
    prior_posesiones: dict[str, float] = field(
        default_factory=lambda: {"points": 300.0, "reb": 300.0, "assists": 300.0}
    )
    # Exponente del ajuste por rival (0 = no se ajusta, 1 = completo).
    peso_rival: dict[str, float] = field(default_factory=lambda: {"reb": 1.0, "assists": 1.0})
    # Varianza / media de cada estadistica con los minutos ya fijos.
    dispersion: dict[str, float] = field(
        default_factory=lambda: {"points": 2.4, "reb": 1.05, "assists": 1.05}
    )
    sd_minutos: float = 6.0
    paliza_umbral: float = 8.0
    paliza_pendiente: float = 0.27  # minutos por punto de margen, titulares
    # Mezcla final de la media: (simulacion, promedio de la temporada, ultimos
    # 10). Ajustada por minimos cuadrados en 2024-25; los promedios traen el
    # rol reciente que la tasa de largo plazo no ve.
    mezcla: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: {
            "points": (0.668, 0.209, 0.166),
            "reb": (0.573, 0.236, 0.213),
            "assists": (0.623, 0.171, 0.226),
        }
    )


def tabla_jugador_partido(jugadores: pd.DataFrame, partidos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por jugador que jugo, con sus posesiones en cancha."""
    info = partidos.set_index("game_id")[["fecha", "season", "season_type", "posesiones", "minutos_juego", "home_id", "away_id"]]
    j = jugadores[jugadores.minutes > 0].join(info, on="game_id", how="inner").copy()
    j["reb"] = j.offensive_rebounds + j.defensive_rebounds
    j["pos"] = j.posesiones * j.minutes / j.minutos_juego
    j["rival"] = np.where(j.team_id == j.home_id, j.away_id, j.home_id)
    return j.sort_values(["athlete_id", "fecha"]).reset_index(drop=True)


@dataclass
class Tasas:
    jugador: pd.DataFrame  # index athlete_id, columnas = STATS (por 100 posesiones)
    rival: pd.DataFrame  # index team_id, factor permitido / liga por estadistica
    liga: dict[str, float]


def tasas(tabla: pd.DataFrame, antes_de, params: ParametrosProps | None = None) -> Tasas:
    """Tasas por 100 posesiones de cada jugador y lo que permite cada defensa."""
    params = params or ParametrosProps()
    t = tabla[tabla.fecha < antes_de]
    liga = {s: float(t[s].sum() / t.pos.sum() * 100) for s in STATS}

    # Peso por recencia en partidos del propio jugador.
    orden = t.groupby("athlete_id").cumcount(ascending=False)
    w = np.power(0.5, orden.values / params.vida_media_partidos)
    pos_w = (t.pos * w).groupby(t.athlete_id).sum()
    filas = {}
    for s in STATS:
        k = params.prior_posesiones[s]
        suma = (t[s] * w).groupby(t.athlete_id).sum()
        filas[s] = (suma + k * liga[s] / 100) / (pos_w + k) * 100
    jug = pd.DataFrame(filas)

    # Lo que permite cada defensa: lo que sus rivales produjeron contra ella en
    # sus ultimos ~25 partidos, por posesion, contra la liga.
    por_partido = t.groupby(["game_id", "rival"])[list(STATS) + ["pos"]].sum().reset_index()
    por_partido = por_partido.merge(t[["game_id", "fecha"]].drop_duplicates("game_id"), on="game_id")
    por_partido = por_partido.sort_values("fecha").groupby("rival").tail(25)
    agg = por_partido.groupby("rival")[list(STATS) + ["pos"]].sum()
    rival = pd.DataFrame({s: (agg[s] / agg.pos * 100) / liga[s] for s in STATS})
    return Tasas(jug, rival, liga)


def promedios(tabla: pd.DataFrame, antes_de, temporada: int) -> pd.DataFrame:
    """Promedio por partido de la temporada y de los ultimos 10, por jugador.

    Con menos de 3 partidos en la temporada, el de la temporada usa sus ultimos
    30 (temporada pasada). Sin historial no hay fila y la mezcla no aplica.
    """
    t = tabla[(tabla.fecha < antes_de) & (tabla.season_type != 3)]
    g = t.groupby("athlete_id")
    ult10 = g[list(STATS)].apply(lambda x: x.tail(10).mean())
    ult30 = g[list(STATS)].apply(lambda x: x.tail(30).mean())
    tt = t[t.season == temporada].groupby("athlete_id")
    temp = tt[list(STATS)].mean()
    temp = temp[tt.size() >= 3].reindex(ult30.index).fillna(ult30)
    return pd.concat({"temporada": temp, "ult10": ult10}, axis=1)


def _rotacion(minutos: dict[int, float], n: int = ROTACION) -> list[int]:
    return [a for a, m in sorted(minutos.items(), key=lambda x: -x[1])[:n] if m >= 8]


def simular_props(
    T: Tasas,
    minutos: dict[str, dict[int, float]],  # lado -> {athlete_id: minutos proyectados}
    equipos: dict[str, int],  # lado -> team_id
    puntos_equipo: dict[str, np.ndarray],  # lado -> puntos simulados del equipo (final)
    margen_casa: np.ndarray,
    pace: float,
    params: ParametrosProps | None = None,
    semilla: int | None = None,
    jugadores: list[int] | None = None,
    prom: pd.DataFrame | None = None,
) -> dict[int, dict[str, np.ndarray]]:
    """Simulaciones por jugador de cada estadistica.

    `jugadores` limita a quien se simula (por omision, la rotacion de 8 de cada
    lado); el reparto de puntos usa siempre a todo el equipo. `prom` (de
    `promedios`) activa la mezcla con los promedios recientes.
    """
    params = params or ParametrosProps()
    rng = np.random.default_rng(semilla)
    n = len(margen_casa)
    out: dict[int, dict[str, np.ndarray]] = {}
    for lado, rival_lado in (("home", "away"), ("away", "home")):
        mins = minutos[lado]
        ids = [a for a, m in mins.items() if m > 0]
        if not ids:
            continue
        m = np.array([mins[a] for a in ids])
        titulares = np.zeros(len(ids), bool)
        titulares[np.argsort(-m)[:5]] = True

        # Minutos simulados: ruido propio + lo que quita una paliza a los
        # titulares, repartido entre la banca.
        exceso = np.maximum(np.abs(margen_casa) - params.paliza_umbral, 0.0)
        quita = params.paliza_pendiente * exceso
        ms = m[None, :] + rng.normal(0, params.sd_minutos, (n, len(ids)))
        ms[:, titulares] -= quita[:, None]
        banca = ~titulares
        if banca.any():
            peso_b = m[banca] / m[banca].sum()
            ms[:, banca] += (quita * titulares.sum())[:, None] * peso_b[None, :]
        ms = np.clip(ms, 0, 48)
        frac = np.where(m[None, :] > 0, ms / m[None, :], 0.0)

        tasa = T.jugador.reindex(ids)
        for s in STATS:
            tasa[s] = tasa[s].fillna(T.liga[s])
        pos_jug = pace * m / 48  # posesiones en cancha esperadas

        # Puntos: parte del marcador del equipo en cada simulacion.
        base_pts = tasa["points"].values * pos_jug / 100
        cuota = base_pts / base_pts.sum()
        media = {"points": cuota[None, :] * puntos_equipo[lado][:, None] * frac}
        rival = equipos[rival_lado]
        for s in ("reb", "assists"):
            f = T.rival[s].get(rival, 1.0) if s in T.rival else 1.0
            f = f ** params.peso_rival.get(s, 0.0)
            media[s] = (tasa[s].values * pos_jug / 100 * f)[None, :] * frac

        quienes = jugadores if jugadores is not None else _rotacion(dict(zip(ids, m)))
        col = {a: k for k, a in enumerate(ids)}
        for a in quienes:
            if a not in col:
                continue
            k = col[a]
            res = {}
            for s in STATS:
                mu = np.maximum(media[s][:, k], 1e-9)
                if prom is not None and a in prom.index:
                    w = params.mezcla[s]
                    base = float(mu.mean())
                    objetivo = w[0] * base + w[1] * prom.at[a, ("temporada", s)] + w[2] * prom.at[a, ("ult10", s)]
                    if base > 0 and objetivo == objetivo:
                        mu = mu * max(objetivo, 0.05) / base
                phi = params.dispersion[s]
                if phi > 1.0001:
                    lam = rng.gamma(mu / (phi - 1), phi - 1)
                else:
                    lam = mu
                res[s] = rng.poisson(lam)
            res["minutos"] = ms[:, k]
            out[a] = res
    return out


def _escalera(valores: np.ndarray, ancho: int) -> dict[str, float]:
    centro = float(np.median(valores))
    base = np.floor(centro) + 0.5
    lineas = np.arange(base - ancho, base + ancho + 1, 1.0)
    lineas = lineas[lineas > 0]
    s = np.sort(valores)
    n = len(s)
    return {
        f"{L:.1f}": round(float(n - np.searchsorted(s, L, side="right")) / n, 4)
        for L in lineas
    }


ANCHO = {"points": 6, "reb": 3, "assists": 3, "pra": 8, "pr": 6, "pa": 6}
NOMBRE = {"points": "puntos", "reb": "rebotes", "assists": "asistencias",
          "pra": "pra", "pr": "puntos_rebotes", "pa": "puntos_asistencias"}


def resumir(sims: dict[str, np.ndarray]) -> dict:
    """Media, mediana, rango 80% y escalera de over por estadistica."""
    valores = {s: sims[s] for s in STATS}
    for c, partes in COMBOS.items():
        valores[c] = sum(sims[p] for p in partes)
    out = {"minutos": round(float(np.mean(sims["minutos"])), 1)}
    for clave, v in valores.items():
        out[NOMBRE[clave]] = {
            "media": round(float(v.mean()), 2),
            "mediana": float(np.median(v)),
            "p10": float(np.percentile(v, 10)),
            "p90": float(np.percentile(v, 90)),
            "overs": _escalera(v, ANCHO[clave]),
        }
    return out


def jugadores_disponibles(jugadores: pd.DataFrame, game_id: int) -> pd.DataFrame:
    """Para el backtest: quienes estaban disponibles en ese partido."""
    g = jugadores[jugadores.game_id == game_id]
    return g[~no_disponible(g.did_not_play, g.reason)]
