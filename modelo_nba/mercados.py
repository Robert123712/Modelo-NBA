"""De las simulaciones a probabilidades por mercado y por linea.

Se publica una escalera de lineas alrededor de la del modelo, no solo la del
modelo: la linea que ofrece la casa casi nunca coincide, y es en ella donde se
juega. Las claves son la linea firmada ("-5.5", "+3.0") como en MLB.

Para lineas enteras existe el push. Se publica solo P(cubre) de cada lado; el
push es lo que falta para 1 (`1 - casa[L] - visita[-L]`).
"""

from __future__ import annotations

import numpy as np

from .simulador import Simulacion


def _escalera(centro: float, ancho: float, paso: float = 0.5) -> np.ndarray:
    c = np.round(centro / paso) * paso
    return np.round(np.arange(c - ancho, c + ancho + paso / 2, paso), 1)


def _firmada(x: float) -> str:
    return f"{x:+.1f}"


def _cubre(margen: np.ndarray, lineas: np.ndarray) -> dict[str, float]:
    """P(margen + linea > 0) para cada linea del lado que recibe esa linea."""
    s = np.sort(margen)
    n = len(s)
    # margen + L > 0  <=>  margen > -L
    return {
        _firmada(L): round(float(n - np.searchsorted(s, -L, side="right")) / n, 4)
        for L in lineas
    }


def _overs(valores: np.ndarray, lineas: np.ndarray) -> dict[str, float]:
    s = np.sort(valores)
    n = len(s)
    return {
        f"{L:.1f}": round(float(n - np.searchsorted(s, L, side="right")) / n, 4)
        for L in lineas
    }


def _resumen(x: np.ndarray) -> dict[str, float]:
    return {
        "media": round(float(x.mean()), 2),
        "mediana": round(float(np.median(x)), 1),
        "p10": round(float(np.percentile(x, 10)), 1),
        "p90": round(float(np.percentile(x, 90)), 1),
    }


def mercados(sim: Simulacion) -> dict:
    margen, total = sim.margen, sim.total
    m1 = sim.casa_1h - sim.visita_1h
    t1 = sim.casa_1h + sim.visita_1h

    centro_spread = -float(np.median(margen))  # linea de la casa
    lineas_casa = _escalera(centro_spread, 8.0)
    centro_1h = -float(np.median(m1))
    lineas_1h = _escalera(centro_1h, 5.0)

    return {
        "ganador": {
            "casa": round(float((margen > 0).mean()), 4),
            "visita": round(float((margen < 0).mean()), 4),
        },
        "tiempo_extra": round(float((sim.casa_reg == sim.visita_reg).mean()), 4),
        "margen": _resumen(margen),
        "total": _resumen(total),
        "spread_casa": _cubre(margen, lineas_casa),
        "spread_visita": _cubre(-margen, -lineas_casa[::-1]),
        "totales": _overs(total, _escalera(float(np.median(total)), 10.0)),
        "team_total_casa": _overs(sim.casa, _escalera(float(np.median(sim.casa)), 6.0)),
        "team_total_visita": _overs(sim.visita, _escalera(float(np.median(sim.visita)), 6.0)),
        "puntos_casa": _resumen(sim.casa),
        "puntos_visita": _resumen(sim.visita),
        "primera_mitad": {
            "casa": round(float((m1 > 0).mean()), 4),
            "empate": round(float((m1 == 0).mean()), 4),
            "visita": round(float((m1 < 0).mean()), 4),
            "margen": _resumen(m1),
            "total": _resumen(t1),
            "spread_casa": _cubre(m1, lineas_1h),
            "spread_visita": _cubre(-m1, -lineas_1h[::-1]),
            "totales": _overs(t1, _escalera(float(np.median(t1)), 6.0)),
        },
    }
