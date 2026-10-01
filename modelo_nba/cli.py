"""Linea de comandos.

    modelo-nba predecir [--fecha AAAA-MM-DD]
    modelo-nba backtest --temporada 2026 [--cada-dias 1]
    modelo-nba calibrar --temporadas 2024 2025
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

import numpy as np


def _predecir(a):
    from .diario import predecir

    fecha = dt.date.fromisoformat(a.fecha) if a.fecha else None
    print(json.dumps(predecir(fecha), ensure_ascii=False))


def _backtest(a):
    from . import backtest, historico
    from .parametros import cargar_parametros

    pr, _ = cargar_parametros()
    p, j = historico.cargar(list(range(a.temporada - 3, a.temporada + 1)))
    res = backtest.correr(p, j, a.temporada, pr, cada_dias=a.cada_dias)
    if a.salida:
        res.to_parquet(a.salida, index=False)
    print(json.dumps(backtest.resumen(res, historico.lineas_de_cierre()), indent=1))


def _calibrar(a):
    """Covarianza del simulador con los residuos walk-forward de esas temporadas."""
    import pandas as pd

    from . import backtest, historico
    from .parametros import cargar_parametros, guardar_parametros
    from .simulador import calibrar

    pr, ps = cargar_parametros()
    partes = []
    for t in a.temporadas:
        p, j = historico.cargar(list(range(t - 3, t + 1)))
        partes.append(backtest.correr(p, j, t, pr, cada_dias=a.cada_dias))
    bt = pd.concat(partes, ignore_index=True)
    residuos = backtest.residuos_por_mitad(bt, ps.parte_1h)
    ps.cov = calibrar(residuos)
    ps.sesgo = np.nanmean(residuos, axis=0)
    guardar_parametros(None, ps)
    print(json.dumps({"n": len(bt), "cov": np.round(ps.cov, 2).tolist(),
                      "sesgo": np.round(ps.sesgo, 2).tolist()}, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="modelo-nba")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("predecir")
    s.add_argument("--fecha")
    s.set_defaults(fn=_predecir)
    s = sub.add_parser("backtest")
    s.add_argument("--temporada", type=int, required=True)
    s.add_argument("--cada-dias", type=int, default=1)
    s.add_argument("--salida")
    s.set_defaults(fn=_backtest)
    s = sub.add_parser("calibrar")
    s.add_argument("--temporadas", type=int, nargs="+", required=True)
    s.add_argument("--cada-dias", type=int, default=1)
    s.set_defaults(fn=_calibrar)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
