import json

import pandas as pd

from modelo_nba.diario import registrar


def _r(gid, generado, antes, valor):
    return {"generated_at": generado, "game_id": gid, "minutos_antes": antes, "proyeccion": {"x": valor}}


def test_oficial_es_la_ultima_con_60_minutos(tmp_path):
    ahora = pd.Timestamp("2026-10-21T20:00Z")
    registrar(tmp_path, "2026-10-21", [_r(1, "a", 180, "temprana")], ahora)
    registrar(tmp_path, "2026-10-21", [_r(1, "b", 75, "t-75")], ahora)
    o = registrar(tmp_path, "2026-10-21", [_r(1, "c", 45, "t-45")], ahora)
    assert o["1"]["proyeccion"]["x"] == "t-75"
    assert o["1"]["tardia"] is False
    guardado = json.loads((tmp_path / "oficiales" / "2026-10-21.json").read_text())
    assert guardado["1"]["proyeccion"]["x"] == "t-75"


def test_sin_corrida_a_tiempo_queda_la_primera_marcada(tmp_path):
    ahora = pd.Timestamp("2026-10-21T20:00Z")
    registrar(tmp_path, "d", [_r(2, "a", 40, "primera")], ahora)
    o = registrar(tmp_path, "d", [_r(2, "b", 10, "segunda")], ahora)
    assert o["2"]["proyeccion"]["x"] == "primera"
    assert o["2"]["tardia"] is True


def test_turnos_del_vigilante():
    from modelo_nba.vigilante import en_ventana, siguiente_turno

    t = lambda s: pd.Timestamp(s)
    assert siguiente_turno(t("2026-10-21T22:00Z")) == t("2026-10-21T22:15Z")
    assert siguiente_turno(t("2026-10-21T22:15Z")) == t("2026-10-21T22:45Z")
    assert siguiente_turno(t("2026-10-21T22:50Z")) == t("2026-10-21T23:15Z")
    assert siguiente_turno(t("2026-10-21T23:59Z")) == t("2026-10-22T00:15Z")
    # 19:00 ET dentro; 05:00 ET fuera; 01:30 ET (noche del partido tardio) dentro.
    assert en_ventana(t("2026-10-21T23:00Z"))
    assert not en_ventana(t("2026-10-22T09:00Z"))
    assert en_ventana(t("2026-10-22T05:30Z"))
