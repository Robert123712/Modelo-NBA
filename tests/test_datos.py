import pandas as pd

from modelo_nba.historico import parse_linescores
from modelo_nba.minutos import no_disponible, repartir


def test_linescores_en_los_dos_formatos_de_hoopr():
    viejo = "[{'value': 22.0} {'value': 17.0} {'value': 27.0} {'value': 24.0}]"
    nuevo = (
        "[{'displayValue': '23', 'period': 1, 'value': 23.0}\n"
        " {'displayValue': '19', 'period': 2, 'value': 19.0}\n"
        " {'value': 30.0, 'displayValue': '30', 'period': 3.0}\n"
        " {'value': 18.0, 'displayValue': '18', 'period': 4.0}\n"
        " {'value': 11.0, 'displayValue': '11', 'period': 5.0}]"
    )
    assert parse_linescores(viejo) == [22, 17, 27, 24]
    assert parse_linescores(nuevo) == [23, 19, 30, 18, 11]
    assert parse_linescores(None) == []


def test_dnp_del_coach_si_esta_disponible():
    dnp = pd.Series([True, True, False, True])
    razon = pd.Series(["COACH'S DECISION", "LEFT ANKLE SPRAIN", "", "Coach's Decision"])
    assert no_disponible(dnp, razon).tolist() == [False, True, False, False]


def test_repartir_suma_240_y_respeta_tope():
    base = {1: 38.0, 2: 36.0, 3: 34.0, 4: 30.0, 5: 28.0, 6: 20.0, 7: 12.0}
    m = repartir(base)
    assert abs(sum(m.values()) - 240) < 1e-6
    assert max(m.values()) <= 40.0 + 1e-9


def test_repartir_redistribuye_baja_proporcional():
    completo = {1: 36.0, 2: 34.0, 3: 32.0, 4: 30.0, 5: 28.0, 6: 24.0, 7: 20.0, 8: 16.0, 9: 20.0}
    sin_estrella = {k: v for k, v in completo.items() if k != 1}
    m = repartir(sin_estrella)
    assert abs(sum(m.values()) - 240) < 1e-6
    assert m[2] > completo[2]


def test_repartir_solo_entran_11():
    # Un roster de 18 (two-way incluidos) no le quita minutos al titular.
    base = {i: 34.0 - 2 * i for i in range(11)} | {100 + i: 10.0 for i in range(7)}
    m = repartir(base)
    assert abs(sum(m.values()) - 240) < 1e-6
    assert all(m[100 + i] == 0 for i in range(7))
    assert abs(m[0] - repartir({i: 34.0 - 2 * i for i in range(11)})[0]) < 1e-9


def test_repartir_sin_historial_usa_minutos_por_defecto():
    m = repartir({1: float("nan"), 2: 30.0, 3: 30.0, 4: 30.0, 5: 30.0, 6: 30.0, 7: 20.0, 8: 20.0})
    assert abs(sum(m.values()) - 240) < 1e-6
    assert m[1] < m[2]


def test_all_star_no_cuenta_como_partido():
    from modelo_nba.historico import es_franquicia
    assert es_franquicia(25) and es_franquicia("1") and es_franquicia(30)
    assert not es_franquicia(32)  # EAST/WEST 2024
    assert not es_franquicia(132374)  # equipos del formato nuevo
    assert not es_franquicia(None)


def _historial_tanque():
    """Un suplente que juega 21 minutos y en los ultimos 8 de la temporada,
    con su equipo tanqueando, juega 36 (el caso de Cody Williams)."""
    from modelo_nba.minutos import minutos_actuales
    partidos, jugadores = [], []
    inicio = pd.Timestamp("2025-10-20", tz="UTC")
    for g in range(70):
        partidos.append(dict(game_id=g, fecha=inicio + pd.Timedelta(days=2 * g), season_type=2, season=2026))
        jugadores.append(dict(game_id=g, athlete_id=7, minutes=36.0 if g >= 62 else 21.0,
                              did_not_play=False, reason=""))
    return pd.DataFrame(partidos), pd.DataFrame(jugadores), minutos_actuales


def test_arranque_de_temporada_no_arrastra_el_cierre_del_ano_pasado():
    p, j, minutos_actuales = _historial_tanque()
    corte = pd.Timestamp("2026-10-21", tz="UTC")
    viejo = minutos_actuales(j, p, corte)[7]
    nuevo = minutos_actuales(j, p, corte, temporada=2027)[7]
    assert viejo > 30  # sin la regla: el cierre manda
    assert abs(nuevo - j.minutes.mean()) < 0.5  # con la regla: su promedio


def test_revision_avisa_minutos_fuera_de_lo_normal():
    from modelo_nba.minutos import revisar
    ref = {1: 21.0, 2: 35.0, 3: 30.0}
    rot = {1: 30.2, 2: 29.0, 3: 31.0}
    assert {a for a, *_ in revisar(rot, ref, minutos_perdidos=0)} == {1}
    # Con bajas grandes, que alguien suba es normal; que baje, no.
    assert revisar({1: 30.2, 2: 25.0}, ref, minutos_perdidos=40) == [(2, 25.0, 35.0)]
    # El que esta en duda baja por su probabilidad de jugar: no es error.
    assert revisar({2: 17.5}, ref, minutos_perdidos=0, en_duda={2}) == []


def _historial_regreso():
    """El 7 es titular, se pierde 3 partidos por lesion y regresa; el 8 es
    suplente en todos."""
    partidos, jugadores = [], []
    inicio = pd.Timestamp("2025-10-21", tz="UTC")
    for g in range(10):
        partidos.append(dict(game_id=g, fecha=inicio + pd.Timedelta(days=2 * g), season_type=2, season=2026,
                             home_id=1, away_id=2))
        fuera = 5 <= g <= 7
        jugadores.append(dict(game_id=g, team_id=1, athlete_id=7, minutes=0.0 if fuera else 34.0,
                              starter=not fuera, did_not_play=fuera, reason="Left Ankle Sprain" if fuera else "",
                              fouls=2.0))
        jugadores.append(dict(game_id=g, team_id=1, athlete_id=8, minutes=18.0, starter=False,
                              did_not_play=False, reason="", fouls=4.0))
    return pd.DataFrame(partidos), pd.DataFrame(jugadores)


def test_rasgos_iguales_en_backtest_y_en_vivo():
    from modelo_nba import minutos as mn
    p, j = _historial_regreso()
    jm = mn.con_rasgos(mn.con_minutos_previos(j, p), p)
    fila = jm[(jm.game_id == 8) & (jm.athlete_id == 7)].iloc[0]
    assert bool(fila.titular_prev) and fila.fuera == 3 and not fila.traspaso and fila.k_temp == 5
    corte = p.fecha[8]
    vivo = mn.rasgos_actuales(j, p, corte, 2026).loc[7]
    assert bool(vivo.titular_prev) and vivo.k_temp == fila.k_temp
    assert mn.juegos_fuera(p, 1, vivo.fecha_prev, corte) == fila.fuera
    assert abs(vivo.faltas36 - fila.faltas36) < 1e-9


def test_correccion_por_contexto():
    from modelo_nba.minutos import corregir
    base = {7: 30.0, 8: 30.0}
    titular = corregir(base, {7: {"titular_prev": True, "k_temp": 20}, 8: {"titular_prev": False, "k_temp": 20}},
                       b2b=False, bajas=0.0)
    assert titular[7] > titular[8]
    regreso = corregir(base, {7: {"titular_prev": True, "fuera": 3, "k_temp": 20},
                              8: {"titular_prev": True, "fuera": 0, "k_temp": 20}}, b2b=False, bajas=0.0)
    assert regreso[7] < regreso[8]
    # Sin rasgos (novato sin historial), la base no se toca.
    assert corregir({9: 12.0}, {}, b2b=True, bajas=30.0) == {9: 12.0}
