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


def test_repartir_sin_historial_usa_minutos_por_defecto():
    m = repartir({1: float("nan"), 2: 30.0, 3: 30.0, 4: 30.0, 5: 30.0, 6: 30.0, 7: 20.0, 8: 20.0})
    assert abs(sum(m.values()) - 240) < 1e-6
    assert m[1] < m[2]
