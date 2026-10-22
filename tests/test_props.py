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
    titular, octavo = plantel[1][0], plantel[1][7]
    # 30 de diferencia: 0.19 * (30 - 12) = 3.4 minutos menos para el titular.
    assert paliza[titular]["minutos"].mean() < cerrado[titular]["minutos"].mean() - 3
    # Se los lleva el fondo de la banca (del noveno para abajo), no el octavo.
    assert abs(paliza[octavo]["minutos"].mean() - cerrado[octavo]["minutos"].mean()) < 0.3


def test_combinados_salen_de_la_misma_simulacion():
    _, T, prom, plantel, mins = _tasas()
    s = _sim(T, plantel, mins, prom=prom, n=4000)
    r = props.resumir(s[plantel[1][0]])
    assert abs(r["pra"]["media"] - sum(r[k]["media"] for k in ("puntos", "rebotes", "asistencias"))) < 0.05
    # Escalera de overs: lineas .5 de uno en uno, decreciente, que cruza el 50%
    # cerca de la mediana y sin colas inservibles.
    esc = r["puntos"]["overs"]
    overs = esc["p"]
    assert esc["desde"] % 1 == 0.5
    assert all(a >= b for a, b in zip(overs, overs[1:]))
    assert all(0.005 <= x <= 0.995 for x in overs)
    cruce = esc["desde"] + next(i for i, x in enumerate(overs) if x < 0.5)
    assert abs(cruce - r["puntos"]["mediana"]) <= 1
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


def _tabla_dvp():
    """Un centro y un guardia contra tres defensas; la 3 regala rebotes al centro."""
    filas = []
    inicio = pd.Timestamp("2025-11-01", tz="UTC")
    for g in range(90):
        rival = g % 3 + 1
        for a, posicion, reb in ((10, "C", 10.0 if rival == 3 else 6.0), (11, "G", 3.0)):
            filas.append(dict(
                game_id=g, athlete_id=a, team_id=9, rival=rival, posicion=posicion,
                fecha=inicio + pd.Timedelta(days=g), season=2026, season_type=2, pos=60.0,
                points=12.0, reb=reb, assists=4.0, three_point_field_goals_attempted=3.0,
            ))
    return pd.DataFrame(filas)


def test_defensa_por_posicion_ve_al_que_regala_rebotes_al_centro():
    t = _tabla_dvp()
    T = props.tasas(t, t.fecha.max() + pd.Timedelta(days=1), props.ParametrosProps(grupo="posicion"))
    assert T.grupo[10] == "C" and T.grupo[11] == "G"
    assert T.dvp.loc[(3, "C"), "reb"] > 1.15
    assert T.dvp.loc[(1, "C"), "reb"] < 0.95
    assert abs(T.dvp.loc[(3, "G"), "reb"] - 1) < 0.02  # al guardia no le cambia


def test_companeros_fuera_suben_el_rebote_de_los_que_quedan():
    _, T, _, plantel, mins = _tasas()
    sano = repartir(dict(zip(plantel[1], mins)))
    sin_uno = repartir({a: m for a, m in zip(plantel[1], mins) if a != plantel[1][0]})
    n = 4000
    pts = {"home": np.full(n, 110.0), "away": np.full(n, 110.0)}
    kw = dict(equipos={"home": 1, "away": 2}, puntos_equipo=pts, margen_casa=np.zeros(n),
              pace=100.0, semilla=1)
    rot = {"home": sin_uno, "away": repartir(dict(zip(plantel[2], mins)))}
    sin = props.simular_props(T, rot, **kw)
    con = props.simular_props(T, rot, params=props.ParametrosProps(beta_bajas={"reb": 1.0, "assists": 1.0}),
                              minutos_completos={"home": sano}, **kw)
    a = plantel[1][1]
    assert con[a]["info"]["bajas"]["reb"] >= 1.0
    assert con[a]["reb"].mean() >= sin[a]["reb"].mean() - 0.1


def test_insight_elige_lo_que_mas_mueve():
    info = {"grupo": "pivot", "por_grupo": ["reb"], "rival": {"points": 1.0, "reb": 1.15, "assists": 1.0},
            "bajas": {"points": 1.0, "reb": 1.0, "assists": 1.0}, "minutos": 30.0,
            "minutos_completo": 30.0}
    medias = {"points": 15.0, "reb": 11.0, "assists": 2.0}
    assert props.insight(info, medias, "DAL") == "DAL permite muchos rebotes a los pívots (+1.4 reb)"
    # Sin ajuste por grupo en rebotes, se explica como del equipo.
    assert props.insight(dict(info, por_grupo=[]), medias, "DAL") == "DAL permite muchos rebotes (+1.4 reb)"
    info["rival"]["reb"] = 1.02
    assert props.insight(info, medias, "DAL") is None  # nada pasa el umbral
    info["minutos_completo"] = 24.0
    assert props.insight(info, medias, "DAL", ausente="Brunson") == "Sin Brunson juega más minutos (+6 min)"
    assert props.insight(info, medias, "DAL", en_duda=True).startswith("En duda")


def test_companeros_fuera_suben_a_los_que_juegan():
    _, T, prom, plantel, mins = _tasas()
    base = _sim(T, plantel, mins, prom=prom, n=4000)
    ausente = plantel[1][8]
    minutos = {"home": repartir(dict(zip(plantel[1], mins))), "away": repartir(dict(zip(plantel[2], mins)))}
    pts = {"home": np.full(4000, 115.0), "away": np.full(4000, 110.0)}
    con = props.simular_props(T, minutos, {"home": 1, "away": 2}, pts, np.full(4000, 5.0), 100.0,
                              semilla=1, prom=prom, fuera={"home": [ausente], "away": []})
    a = plantel[1][0]
    esperado = props.ParametrosProps().correccion["reb"]["fuera"] * prom.at[ausente, ("hab", "reb")] / 10
    assert abs((con[a]["reb"].mean() - base[a]["reb"].mean()) - esperado) < 0.15
    # El rival no cambia.
    b = plantel[2][0]
    assert abs(con[b]["reb"].mean() - base[b]["reb"].mean()) < 0.1
