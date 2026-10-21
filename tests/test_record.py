import json

import pandas as pd

from modelo_nba import record


def _oficial(gid, p_casa, spread, total, iv_m, iv_t, version="nba-0.3.0"):
    return {gid: {"model_version": version, "proyeccion": {
        "win_probability": {"home": p_casa, "away": 1 - p_casa},
        "spread": {"home": spread, "away": -spread}, "total_points": total,
        "intervals_80": {"home_margin": iv_m, "total": iv_t}}}}


def test_record_con_el_formato_de_edgebook(tmp_path):
    d = tmp_path / "oficiales"
    d.mkdir()
    (d / "2026-10-20.json").write_text(json.dumps({
        **_oficial("1", 0.7, -5.0, 220.0, [-10, 20], [200, 240]),
        **_oficial("2", 0.4, 3.0, 230.0, [-15, 10], [210, 250]),
        **_oficial("3", 0.5, 0.0, 225.0, [-10, 10], [205, 245]),  # sin jugar aun
    }))
    partidos = pd.DataFrame({"game_id": [1, 2], "home_pts": [110.0, 100.0], "away_pts": [100.0, 120.0]})
    cierre = pd.DataFrame({"game_id": [1, 2], "linea_casa": [-6.0, 2.0], "total_cierre": [215.0, 222.0]})
    r = record.construir(d, partidos, cierre, "2026-10-21T12:00:00Z")
    assert r["schema_version"] == "1.0" and r["sport"] == "NBA"
    (v,) = r["versions"]
    assert v["graded"] == 2 and v["pending"] == 1
    ml = v["markets"]["moneyline"]
    assert ml["hit_rate"] == 1.0  # 0.7 casa gano; 0.4 casa perdio
    assert ml["brier"] == round(((0.7 - 1) ** 2 + (0.4 - 0) ** 2) / 2, 4)
    assert v["markets"]["closing_moneyline"]["n"] == 2
    # Margen esperado = -spread: 5 vs real 10 -> -5; -3 vs real -20 -> 17.
    assert v["projected_margin"]["mae"] == 11.0
    assert v["closing_line"]["margin"]["mae"] == round((abs(6 - 10) + abs(-2 + 20)) / 2, 3)
    assert v["interval_coverage"]["total"]["covered"] == 1.0
