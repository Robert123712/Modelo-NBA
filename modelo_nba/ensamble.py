"""El arbitro: combina los cuatro motores con pesos que dependen del contexto.

Cada motor ve el partido distinto y se equivoca distinto. Promediarlos ya
ayuda, pero no confian igual en todas las situaciones:

* Fase de la temporada (juegos que lleva el equipo con menos). Al inicio los
  motores de equipo (Elo, eficiencia, cuatro factores) arrastran el ano
  pasado y no saben del roster nuevo; el de jugadores si.
* Bajas (la mayor fraccion de minutos habituales que le falta a alguno de los
  dos). Los motores de equipo no ven quien falta hoy; el de jugadores si.

Los pesos no se ponen a mano: se aprenden de las predicciones walk-forward de
temporadas pasadas, minimizando el error cuadratico con pesos no negativos que
suman 1 (para que se lean como "confio 60% en este"). Un grupo con pocos
partidos se encoge hacia los pesos globales, para que una racha de 80
partidos no decida la regla.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

MOTORES_MARGEN = ["jugadores", "elo", "equipos", "factores"]
MOTORES_TOTAL = ["jugadores", "equipos", "factores"]
UMBRAL_BAJAS = 0.15
CONTRACCION = 150.0  # partidos ficticios con los pesos globales


def fase(jugados: int) -> str:
    if jugados < 10:
        return "inicio"
    if jugados < 30:
        return "media"
    return "madura"


def grupo(jugados: int, bajas: float) -> str:
    return f"{fase(jugados)}|{'con_bajas' if bajas >= UMBRAL_BAJAS else 'normal'}"


def _convexos(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """Pesos >= 0 que suman 1 y un sesgo libre, por minimos cuadrados."""
    k = X.shape[1]
    Xc, yc = X - X.mean(0), y - y.mean()
    res = minimize(
        lambda w: np.mean((yc - Xc @ w) ** 2),
        np.full(k, 1 / k),
        method="SLSQP",
        bounds=[(0, 1)] * k,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
    )
    w = np.clip(res.x, 0, None)
    w /= w.sum()
    return w, float(y.mean() - X.mean(0) @ w)


@dataclass
class Arbitro:
    pesos_margen: dict[str, dict[str, float]] = field(default_factory=dict)
    pesos_total: dict[str, dict[str, float]] = field(default_factory=dict)
    sesgo_margen: dict[str, float] = field(default_factory=dict)
    sesgo_total: dict[str, float] = field(default_factory=dict)

    def _pesos(self, tabla, g):
        return tabla.get(g) or tabla["global"]

    def combinar(self, margenes: dict[str, float], totales: dict[str, float],
                 jugados: int, bajas: float) -> dict:
        """Margen y total combinados, con los pesos que se usaron.

        Un motor sin prediccion (equipo sin historial) se saca y los pesos de
        los demas se reescalan.
        """
        g = grupo(jugados, bajas)

        def mezcla(valores, pesos, sesgo):
            usados = {k: w for k, w in pesos.items() if k in valores and np.isfinite(valores[k])}
            s = sum(usados.values())
            if s <= 0:
                return valores["jugadores"], {"jugadores": 1.0}
            usados = {k: w / s for k, w in usados.items()}
            return sum(w * valores[k] for k, w in usados.items()) + sesgo, usados

        m, wm = mezcla(margenes, self._pesos(self.pesos_margen, g), self.sesgo_margen.get(g, self.sesgo_margen.get("global", 0.0)))
        t, wt = mezcla(totales, self._pesos(self.pesos_total, g), self.sesgo_total.get(g, self.sesgo_total.get("global", 0.0)))
        return {"margen": m, "total": t, "grupo": g, "pesos_margen": wm, "pesos_total": wt}

    def a_dict(self) -> dict:
        r = lambda d: {k: {m: round(w, 4) for m, w in v.items()} for k, v in d.items()}
        return {
            "pesos_margen": r(self.pesos_margen),
            "pesos_total": r(self.pesos_total),
            "sesgo_margen": {k: round(v, 3) for k, v in self.sesgo_margen.items()},
            "sesgo_total": {k: round(v, 3) for k, v in self.sesgo_total.items()},
        }

    @classmethod
    def de_dict(cls, d: dict) -> "Arbitro":
        return cls(d["pesos_margen"], d["pesos_total"], d["sesgo_margen"], d["sesgo_total"])


def ajustar(bt: pd.DataFrame, por_contexto: bool = True) -> Arbitro:
    """Aprende los pesos de un backtest con las columnas m_* y t_* de cada motor."""
    b = bt.copy()
    b["margen"] = b.real_reg_casa - b.real_reg_visita
    b["total"] = b.real_reg_casa + b.real_reg_visita
    b["grupo"] = [grupo(j, x) for j, x in zip(b.jugados, b.bajas)]
    a = Arbitro()
    for objetivo, motores, pref, pesos, sesgos in (
        ("margen", MOTORES_MARGEN, "m_", a.pesos_margen, a.sesgo_margen),
        ("total", MOTORES_TOTAL, "t_", a.pesos_total, a.sesgo_total),
    ):
        cols = [pref + m for m in motores]
        ok = b.dropna(subset=cols + [objetivo])
        wg, sg = _convexos(ok[cols].values, ok[objetivo].values)
        pesos["global"] = dict(zip(motores, wg.tolist()))
        sesgos["global"] = sg
        if not por_contexto:
            continue
        for g, x in ok.groupby("grupo"):
            w, s = _convexos(x[cols].values, x[objetivo].values) if len(x) >= 30 else (wg, sg)
            n = len(x)
            w = (n * w + CONTRACCION * wg) / (n + CONTRACCION)
            pesos[g] = dict(zip(motores, (w / w.sum()).tolist()))
            sesgos[g] = (n * s + CONTRACCION * sg) / (n + CONTRACCION)
    return a


def aplicar(a: Arbitro, bt: pd.DataFrame) -> pd.DataFrame:
    """Agrega margen_ens, total_ens y el grupo a un backtest."""
    filas = []
    for r in bt.itertuples():
        c = a.combinar(
            {m: getattr(r, f"m_{m}") for m in MOTORES_MARGEN},
            {m: getattr(r, f"t_{m}") for m in MOTORES_TOTAL},
            r.jugados, r.bajas,
        )
        filas.append((c["margen"], c["total"], c["grupo"]))
    out = bt.copy()
    out[["margen_ens", "total_ens", "grupo"]] = pd.DataFrame(filas, index=bt.index)
    return out
