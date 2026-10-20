import json

import pandas as pd

from modelo_nba import seguimiento


def _oficial(tmp_path):
    rec = {
        "proyeccion": {"home": {"code": "DET"}, "away": {"code": "BOS"}},
        "props": [
            {"a": 1, "j": "Uno", "lado": "away", "min": 34.0,
             "s": {k: [20.0, 12.0, 28.0] for k in seguimiento.STATS},
             "prom": {k: 18.0 for k in seguimiento.STATS}},
            {"a": 2, "j": "Dos", "lado": "home", "min": 30.0,
             "s": {k: [10.0, 5.0, 15.0] for k in seguimiento.STATS}},
            {"a": 3, "j": "Tres", "lado": "home", "min": 20.0,
             "s": {k: [8.0, 3.0, 13.0] for k in seguimiento.STATS}},
        ],
    }
    d = tmp_path / "oficiales"
    d.mkdir()
    (d / "2026-10-20.json").write_text(json.dumps({"77": rec}))
    return d


def _box():
    filas = []
    for a, mins, pts, dnp in ((1, 35, 30, False), (2, 28, 9, False), (3, 0, 0, True)):
        filas.append(dict(game_id=77, athlete_id=a, minutes=mins, did_not_play=dnp, points=pts,
                          offensive_rebounds=1, defensive_rebounds=4, assists=3))
    return pd.DataFrame(filas)


def test_califica_contra_el_box_score(tmp_path):
    d = _oficial(tmp_path)
    r = seguimiento.calificar(d, _box(), pd.DataFrame({"game_id": [77]}))
    assert r["jugadores_partido"] == 2  # el que no jugo no cuenta
    pts = r["resumen"]["puntos"]
    assert pts["n"] == 2
    assert pts["error_modelo"] == round((abs(20 - 30) + abs(10 - 9)) / 2, 2)
    assert pts["error_promedio"] == 12.0 and pts["n_promedio"] == 1  # solo Uno trae promedio
    assert pts["en_rango80"] == 0.5  # 30 se sale de 12-28; 9 cae en 5-15
    uno = next(x for x in r["ultimo_dia"]["jugadores"] if x["jugador"] == "Uno")
    assert uno["puntos"] == [20.0, 30.0, 12.0, 28.0] and uno["rival"] == "DET"
    assert r["por_jugador"]["1"][0]["puntos"] == [20.0, 30.0]


def test_partido_sin_jugar_queda_pendiente(tmp_path):
    d = _oficial(tmp_path)
    r = seguimiento.calificar(d, _box(), pd.DataFrame({"game_id": [1]}))
    assert r["jugadores_partido"] == 0 and r["ultimo_dia"] is None
