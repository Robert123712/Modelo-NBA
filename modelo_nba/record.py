"""Record del modelo NBA para Edgebook (data/edgebook-metrics.json).

Califica la prediccion OFICIAL de cada partido (la ultima con 60 minutos de
anticipacion) contra el marcador final, con el mismo formato que publica NFL:
ganador (Brier, aciertos, calibracion), error del margen y del total, y
cobertura del rango 80%. La linea de cierre de consenso (hoopR, The Odds API)
entra solo para comparar: si el modelo no le gana, no aporta nada que no
estuviera ya en el precio.

hoopR trae spread y total de cierre, no moneyline. La probabilidad del cierre
sale del spread con una normal de desviacion 12.5, la que mejor califica el
cierre en 2023-26 (Brier plano entre 12 y 13; el margen real se desvia 13.7
del spread).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

SCHEMA_VERSION = "1.0"
SPORT = "NBA"
MINIMO_SIGNIFICATIVO = 100
TRAMOS = [(0.0, 0.35), (0.35, 0.45), (0.45, 0.50), (0.50, 0.55), (0.55, 0.65), (0.65, 1.01)]
SIGMA_CIERRE = 12.5


def _binario(pares: list[tuple[float, int]], referencia: float = 0.25) -> dict | None:
    if not pares:
        return None
    p = np.array([x for x, _ in pares], float)
    y = np.array([r for _, r in pares], float)
    c = np.clip(p, 1e-9, 1 - 1e-9)
    calibracion = []
    for bajo, alto in TRAMOS:
        dentro = (p >= bajo) & (p < alto)
        if dentro.sum():
            calibracion.append({"from": bajo, "to": alto, "n": int(dentro.sum()),
                                "predicted": round(float(p[dentro].mean()), 4),
                                "observed": round(float(y[dentro].mean()), 4)})
    return {
        "n": len(pares),
        "base_rate": round(float(y.mean()), 4),
        "brier": round(float(np.mean((p - y) ** 2)), 4),
        "log_loss": round(float(-np.mean(y * np.log(c) + (1 - y) * np.log(1 - c))), 4),
        "hit_rate": round(float(np.mean((p >= 0.5) == (y == 1))), 4),
        "baseline_brier": referencia,
        "calibration": calibracion,
    }


def _resumen(valores: list[float]) -> dict:
    n = len(valores)
    media = sum(valores) / n
    return {"n": n, "mae": round(sum(abs(v) for v in valores) / n, 3), "bias": round(media, 3),
            "std_error": round((sum((v - media) ** 2 for v in valores) / n / n) ** 0.5, 4)}


def _error(fechados: list[tuple[str, float]]) -> dict | None:
    """Error de un pronostico numerico (prediccion - real), con su desglose por mes."""
    if not fechados:
        return None
    por_mes = defaultdict(list)
    for fecha, e in fechados:
        por_mes[fecha[:7]].append(e)
    return {**_resumen([e for _, e in fechados]),
            "by_month": [{"month": m, **_resumen(v)} for m, v in sorted(por_mes.items())]}


def _cobertura(marcas: list[bool], nominal: float = 0.8) -> dict | None:
    if not marcas:
        return None
    return {"n": len(marcas), "covered": round(float(np.mean(marcas)), 4), "nominal": nominal}


def oficiales(dir_oficiales: Path) -> dict[str, dict[str, dict]]:
    """model_version -> game_id -> registro oficial (con su fecha)."""
    por_version: dict[str, dict[str, dict]] = defaultdict(dict)
    for ruta in sorted(dir_oficiales.glob("*.json")):
        for gid, rec in json.loads(ruta.read_text()).items():
            por_version[rec.get("model_version", "desconocida")][gid] = {**rec, "fecha": ruta.stem}
    return por_version


def construir(dir_oficiales: Path, partidos: pd.DataFrame, cierre: pd.DataFrame | None,
              generado: str) -> dict:
    reales = {
        str(int(r.game_id)): (float(r.home_pts), float(r.away_pts))
        for r in partidos.itertuples() if r.home_pts == r.home_pts and r.away_pts == r.away_pts
    }
    lineas = {} if cierre is None else {
        str(int(r.game_id)): (r.linea_casa, r.total_cierre) for r in cierre.itertuples()
    }
    versiones = []
    for version, juegos in oficiales(dir_oficiales).items():
        mercados = defaultdict(list)
        margen, total, c_margen, c_total = [], [], [], []
        dentro = {"margin": [], "total": []}
        fechas, pendientes = [], 0
        for gid, rec in sorted(juegos.items()):
            if gid not in reales:
                pendientes += 1
                continue
            casa, visita = reales[gid]
            real_m, real_t = casa - visita, casa + visita
            p = rec["proyeccion"]
            fechas.append(rec["fecha"])
            gana = 1 if real_m > 0 else 0  # en NBA no hay empate
            mercados["moneyline"].append((p["win_probability"]["home"], gana))
            # Spread con el signo de la casa: -4.1 es el local favorito por 4.1.
            margen.append((rec["fecha"], -p["spread"]["home"] - real_m))
            total.append((rec["fecha"], p["total_points"] - real_t))
            linea, tot = lineas.get(gid, (None, None))
            if linea is not None and linea == linea:
                c_margen.append((rec["fecha"], -linea - real_m))
                mercados["closing_moneyline"].append((float(norm.cdf(-linea / SIGMA_CIERRE)), gana))
            if tot is not None and tot == tot:
                c_total.append((rec["fecha"], tot - real_t))
            iv = p.get("intervals_80") or {}
            if iv.get("home_margin"):
                dentro["margin"].append(iv["home_margin"][0] <= real_m <= iv["home_margin"][1])
            if iv.get("total"):
                dentro["total"].append(iv["total"][0] <= real_t <= iv["total"][1])
        versiones.append({
            "model_version": version,
            "unlabeled": False,
            "from": min(fechas) if fechas else None,
            "to": max(fechas) if fechas else None,
            "graded": len(fechas),
            "pending": pendientes,
            "significant": len(fechas) >= MINIMO_SIGNIFICATIVO,
            "markets": {k: _binario(v) for k, v in mercados.items() if v},
            "projected_total": _error(total),
            "projected_margin": _error(margen),
            "closing_line": {"total": _error(c_total), "margin": _error(c_margen)},
            "interval_coverage": {"margin": _cobertura(dentro["margin"]), "total": _cobertura(dentro["total"])},
            "_ultima": max((r["fecha"] for r in juegos.values()), default=""),
        })
    # Primero la version que corre hoy.
    versiones.sort(key=lambda v: v.pop("_ultima"), reverse=True)
    return {"schema_version": SCHEMA_VERSION, "sport": SPORT, "generated_at": generado,
            "minimum_meaningful": MINIMO_SIGNIFICATIVO, "versions": versiones[:20]}
