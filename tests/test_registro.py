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
