"""Monte Carlo de un partido: dos mitades, cierre del reglamento y tiempos extra.

Cada simulacion saca los puntos de cada equipo en cada mitad de una normal
multivariada de 4 dimensiones (1a casa, 2a casa, 1a visita, 2a visita). Las
medias vienen de la proyeccion; la covarianza se estima con los residuos del
backtest walk-forward, asi que ya incluye el error del propio modelo y no solo
el azar del partido. Por eso no se pone a mano.

Sobre eso van dos cosas que una normal no sabe:

* El cierre. En la NBA el reglamento termina empatado ~5% de las veces, mas del
  doble de lo que da una normal, porque el que pierde por 1-3 al final busca
  el empate. Se reproduce moviendo a empate una fraccion de los finales por
  1, 2 y 3 puntos (`al_empate`), calibrada con 2022-2026.
* Los tiempos extra, de 5 minutos, hasta que alguien gane.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Covarianza de residuos por mitad, en el orden (1a casa, 2a casa, 1a visita,
# 2a visita). Valores por defecto; `calibrar` los reemplaza con el backtest.
COV_DEFECTO = np.array([
    [60.0, 5.0, 15.0, 0.0],
    [5.0, 65.0, 0.0, 18.0],
    [15.0, 0.0, 60.0, 5.0],
    [0.0, 18.0, 5.0, 65.0],
])


@dataclass
class ParametrosSim:
    parte_1h: float = 0.5048  # fraccion de los puntos de reglamento en la 1a mitad
    cov: np.ndarray = field(default_factory=lambda: COV_DEFECTO.copy())
    # Media de los residuos walk-forward, mismo orden que `cov`. Corrige lo que
    # el modelo se pasa o se queda corto de forma sistematica en cada mitad.
    sesgo: np.ndarray = field(default_factory=lambda: np.zeros(4))
    # Probabilidad de que un final por |k| puntos termine empatado.
    al_empate: dict[int, float] = field(default_factory=lambda: {1: 0.30, 2: 0.10, 3: 0.08})
    # Puntos por equipo en un OT respecto a 5/48 de su proyeccion: los OT son
    # mas lentos y con mas faltas que el ritmo del partido.
    factor_ot: float = 0.90
    sd_ot: float = 4.2
    rho_ot: float = 0.25
    simulaciones: int = 20000

    def a_dict(self) -> dict:
        return {
            "parte_1h": self.parte_1h,
            "cov": np.asarray(self.cov).round(3).tolist(),
            "sesgo": np.asarray(self.sesgo).round(3).tolist(),
            "al_empate": {str(k): v for k, v in self.al_empate.items()},
            "factor_ot": self.factor_ot,
            "sd_ot": self.sd_ot,
            "rho_ot": self.rho_ot,
            "simulaciones": self.simulaciones,
        }

    @classmethod
    def de_dict(cls, d: dict) -> "ParametrosSim":
        return cls(
            parte_1h=d["parte_1h"],
            cov=np.array(d["cov"]),
            sesgo=np.array(d.get("sesgo", [0.0] * 4)),
            al_empate={int(k): v for k, v in d["al_empate"].items()},
            factor_ot=d["factor_ot"],
            sd_ot=d["sd_ot"],
            rho_ot=d["rho_ot"],
            simulaciones=d.get("simulaciones", 20000),
        )


@dataclass
class Simulacion:
    casa_1h: np.ndarray
    visita_1h: np.ndarray
    casa_reg: np.ndarray
    visita_reg: np.ndarray
    casa: np.ndarray  # final, con OT
    visita: np.ndarray

    @property
    def margen(self):
        return self.casa - self.visita

    @property
    def total(self):
        return self.casa + self.visita


def simular(
    puntos_casa: float,
    puntos_visita: float,
    params: ParametrosSim | None = None,
    semilla: int | None = None,
) -> Simulacion:
    """`puntos_*` son los esperados en reglamento."""
    p = params or ParametrosSim()
    rng = np.random.default_rng(semilla)
    n = p.simulaciones
    s = p.parte_1h
    medias = np.array([
        s * puntos_casa, (1 - s) * puntos_casa,
        s * puntos_visita, (1 - s) * puntos_visita,
    ]) + p.sesgo
    L = np.linalg.cholesky(p.cov)
    x = medias + rng.standard_normal((n, 4)) @ L.T
    x = np.maximum(np.rint(x), 0)
    c1, c2, v1, v2 = x.T
    casa_reg, visita_reg = c1 + c2, v1 + v2

    # Cierre: parte de los finales cerrados se van a empate. Se ajusta al lado
    # que iba perdiendo, que es el que anota para empatar.
    m = casa_reg - visita_reg
    u = rng.random(n)
    for k, q in p.al_empate.items():
        mover = (np.abs(m) == k) & (u < q)
        casa_reg = np.where(mover & (m < 0), casa_reg + k, casa_reg)
        visita_reg = np.where(mover & (m > 0), visita_reg + k, visita_reg)
        c2 = np.where(mover & (m < 0), c2 + k, c2)
        v2 = np.where(mover & (m > 0), v2 + k, v2)
    casa, visita = casa_reg.copy(), visita_reg.copy()

    # Tiempos extra.
    mu_c = puntos_casa * 5 / 48 * p.factor_ot
    mu_v = puntos_visita * 5 / 48 * p.factor_ot
    a, b = np.sqrt((1 + p.rho_ot) / 2), np.sqrt((1 - p.rho_ot) / 2)
    empatados = casa == visita
    for _ in range(10):
        k = int(empatados.sum())
        if not k:
            break
        z1, z2 = rng.standard_normal((2, k))
        casa[empatados] += np.maximum(np.rint(mu_c + p.sd_ot * (a * z1 + b * z2)), 0)
        visita[empatados] += np.maximum(np.rint(mu_v + p.sd_ot * (a * z1 - b * z2)), 0)
        empatados = casa == visita
    # Diez OT empatados no pasa; si pasara, se decide a moneda para no dejar
    # empates en un deporte que no los tiene.
    if empatados.any():
        casa[empatados] += rng.integers(0, 2, int(empatados.sum())) * 2 - 1

    return Simulacion(c1, v1, casa_reg, visita_reg, casa, visita)


def calibrar(residuos: np.ndarray) -> np.ndarray:
    """Covarianza de residuos (n x 4) en el orden de la simulacion."""
    r = residuos[~np.isnan(residuos).any(axis=1)]
    return np.cov(r, rowvar=False)
