import numpy as np
import pandas as pd

from modelo_nba import props
from modelo_nba.minutos import repartir

from .test_ratings import _liga


def _tasas():
    p, j, *_ , plantel, mins = _liga(semilla=3, juegos=300)
    tabla = props.tabla_jugador_partido(j, p)
    corte = p.fecha.max() + pd.Timedelta(days=1)
    return tabla, props.tasas(tabla, corte), props.promedios(tabla, corte, 2026), plantel, mins


def _sim(T, plantel, mins, puntos=(115.0, 110.0), margen=None, prom=None, n=20000):
    minutos = {
        "home": repartir(dict(zip(plantel[1], mins))),
        "away": repartir(dict(zip(plantel[2], mins))),
    }
    pts = {"home": np.full(n, puntos[0]), "away": np.full(n, puntos[1])}
    m = np.full(n, puntos[0] - puntos[1]) if margen is None else np.full(n, margen)
    return props.simular_props(T, minutos, {"home": 1, "away": 2}, pts, m, 100.0,
                               semilla=1, prom=prom)


def test_los_puntos_de_la_rotacion_no_contradicen_el_marcador():
    _, T, _, plantel, mins = _tasas()
    s = _sim(T, plantel, mins, n=4000)
    assert len([a for a in s if a in plantel[1]]) == 8  # rotacion de 8
    # Los 8 se llevan casi todo lo del equipo (el noveno juega 16 minutos).
    suma = sum(s[a]["points"].mean() for a in plantel[1] if a in s)
    assert 0.8 * 115 < suma < 115


def test_paliza_le_quita_minutos_a_los_titulares():
    _, T, _, plantel, mins = _tasas()
    cerrado = _sim(T, plantel, mins, margen=0, n=4000)
    paliza = _sim(T, plantel, mins, margen=30, n=4000)
    titular, banca = plantel[1][0], plantel[1][7]
    assert paliza[titular]["minutos"].mean() < cerrado[titular]["minutos"].mean() - 4
    assert paliza[banca]["minutos"].mean() > cerrado[banca]["minutos"].mean()


def test_combinados_salen_de_la_misma_simulacion():
    _, T, prom, plantel, mins = _tasas()
    s = _sim(T, plantel, mins, prom=prom, n=4000)
    r = props.resumir(s[plantel[1][0]])
    assert abs(r["pra"]["media"] - sum(r[k]["media"] for k in ("puntos", "rebotes", "asistencias"))) < 0.05
    # Escalera de overs: decreciente y centrada en la mediana.
    overs = list(r["puntos"]["overs"].values())
    assert all(a >= b for a, b in zip(overs, overs[1:]))
    assert r["puntos"]["p10"] <= r["puntos"]["mediana"] <= r["puntos"]["p90"]


def test_la_mezcla_acerca_la_media_a_los_promedios():
    _, T, prom, plantel, mins = _tasas()
    a = plantel[1][0]
    falso = prom.copy()
    falso.loc[a, ("temporada", "reb")] = 30.0
    falso.loc[a, ("ult10", "reb")] = 30.0
    sin = _sim(T, plantel, mins, n=4000)[a]["reb"].mean()
    con = _sim(T, plantel, mins, prom=falso, n=4000)[a]["reb"].mean()
    assert con > sin + 5
