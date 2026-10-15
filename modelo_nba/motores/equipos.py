"""Motor 3: eficiencia de equipo ajustada por rival.

Cada equipo tiene un rating de ataque y uno de defensa en puntos por 100
posesiones, ajustados por la calidad de los rivales que enfrento (anotarle 120
a la peor defensa no vale lo mismo que a la mejor). Es el metodo de KenPom
llevado a la NBA, con ridge y memoria corta.

Ve al equipo como un todo: captura el sistema y la forma reciente, pero no
sabe quien falta hoy. Esa es justo la debilidad que cubre el motor de
jugadores, y la razon de combinarlos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp


@dataclass
class ParametrosEquipos:
    vida_media: float = 90.0  # dias; afinado en 2023-24 y 2024-25
    lambda_equipo: float = 5.0
    vida_media_pace: float = 30.0
    lambda_pace: float = 1.0


@dataclass
class RatingsEquipo:
    mu: dict[int, float]
    localia: float
    ataque: dict[int, float]
    defensa: dict[int, float]
    pace_base: dict[int, float]
    pace_equipo: dict[int, float]

    def predecir(self, casa: int, visita: int, temporada: int, neutral: bool) -> tuple[float, float]:
        """Puntos de reglamento esperados (casa, visita)."""
        mu = self.mu.get(temporada, self.mu[max(self.mu)])
        loc = 0.0 if neutral else self.localia
        ortg_c = mu + loc + self.ataque.get(casa, 0.0) - self.defensa.get(visita, 0.0)
        ortg_v = mu - loc + self.ataque.get(visita, 0.0) - self.defensa.get(casa, 0.0)
        pace = (self.pace_base.get(temporada, self.pace_base[max(self.pace_base)])
                + self.pace_equipo.get(casa, 0.0) + self.pace_equipo.get(visita, 0.0))
        return ortg_c * pace / 100, ortg_v * pace / 100


def _pesos(partidos, corte, vida_media):
    edad = (corte - partidos.fecha).dt.total_seconds().values / 86400.0
    return np.power(0.5, edad / vida_media) * partidos.posesiones.values / 100


def ajustar(partidos: pd.DataFrame, corte: pd.Timestamp, params: ParametrosEquipos | None = None) -> RatingsEquipo:
    params = params or ParametrosEquipos()
    p = partidos[partidos.fecha < corte].reset_index(drop=True)
    n = len(p)
    equipos = np.sort(np.unique(np.r_[p.home_id.values, p.away_id.values]))
    e_idx = {e: k for k, e in enumerate(equipos)}
    temporadas = np.sort(p.season.unique())
    t_idx = {t: k for k, t in enumerate(temporadas)}
    E, T = len(equipos), len(temporadas)

    w = _pesos(p, corte, params.vida_media)
    w2 = np.r_[w, w]
    filas = np.arange(2 * n)
    casa = p.home_id.map(e_idx).values
    visita = p.away_id.map(e_idx).values
    of = np.r_[casa, visita]
    de = np.r_[visita, casa]
    tcol = np.r_[p.season.map(t_idx).values, p.season.map(t_idx).values]
    loc = np.where(p.neutral.values, 0.0, 1.0)
    X = sp.hstack([
        sp.csr_matrix((np.ones(2 * n), (filas, tcol)), shape=(2 * n, T)),
        sp.csr_matrix(np.r_[loc, -loc][:, None]),
        sp.csr_matrix((np.ones(2 * n), (filas, of)), shape=(2 * n, E)),
        sp.csr_matrix((-np.ones(2 * n), (filas, de)), shape=(2 * n, E)),
    ]).tocsr()
    y = np.r_[100 * p.home_pts.values / p.posesiones.values,
              100 * p.away_pts.values / p.posesiones.values]
    pen = np.r_[np.zeros(T), 0.0, np.full(2 * E, params.lambda_equipo)]
    Xw = X.multiply(w2[:, None]).tocsr()
    A = (Xw.T @ X).toarray() + np.diag(pen) + 1e-6 * np.eye(X.shape[1])
    beta = np.linalg.solve(A, Xw.T @ y)

    # Pace con su propia memoria.
    wp = _pesos(p, corte, params.vida_media_pace)
    yp = 48 * p.posesiones.values / p.minutos_juego.values
    Xp = np.zeros((n, T + E))
    Xp[np.arange(n), p.season.map(t_idx).values] = 1.0
    Xp[np.arange(n), T + casa] += 1.0
    Xp[np.arange(n), T + visita] += 1.0
    Xpw = Xp * wp[:, None]
    bp = np.linalg.solve(Xpw.T @ Xp + np.diag(np.r_[np.zeros(T), np.full(E, params.lambda_pace)])
                         + 1e-6 * np.eye(T + E), Xpw.T @ yp)

    return RatingsEquipo(
        mu={int(t): float(v) for t, v in zip(temporadas, beta[:T])},
        localia=float(beta[T]),
        ataque={int(e): float(v) for e, v in zip(equipos, beta[T + 1 : T + 1 + E])},
        defensa={int(e): float(v) for e, v in zip(equipos, beta[T + 1 + E :])},
        pace_base={int(t): float(v) for t, v in zip(temporadas, bp[:T])},
        pace_equipo={int(e): float(v) for e, v in zip(equipos, bp[T:])},
    )
