import numpy as np

from modelo_nba import video
from modelo_nba.simulador import ParametrosSim, simular


def _props(rng, n, media):
    return {
        "points": rng.poisson(media, n), "reb": rng.poisson(6, n), "assists": rng.poisson(4, n),
        "minutos": np.full(n, 32.0), "info": {"minutos": 32.0},
    }


def test_construir_cuadra_con_la_simulacion():
    sim = simular(112, 108, ParametrosSim(simulaciones=4000), semilla=7)
    rng = np.random.default_rng(1)
    sims_props = {1: _props(rng, 4000, 24), 2: _props(rng, 4000, 18)}
    g = {"game_id": 9, "starts_at": "2026-11-13T00:00Z", "home_abbr": "PHI", "away_abbr": "TOR",
         "home_id": 20, "away_id": 28, "home_nombre": "Philadelphia 76ers", "away_nombre": "Toronto Raptors"}
    d = video.construir(g, sim, sims_props, {"home": {1: 34.0}, "away": {2: 33.0}}, {1: "Uno", 2: "Dos"})

    assert d["simulaciones"] == 4000
    assert d["victorias"]["home"] + d["victorias"]["away"] == 4000
    assert d["victorias"]["home"] == int((sim.casa > sim.visita).sum())
    assert sum(d["margen"]["cuentas"]) == 4000
    assert len(d["muestra"]) == video.MUESTRA and set(d["muestra"]) <= {"h", "a"}
    assert len(d["cinta"]) == video.CINTA and d["cinta"][0]["gana"] in ("PHI", "TOR")
    uno = d["jugadores"]["home"][0]
    assert uno["jugador"] == "Uno"
    assert uno["mejor"]["points"] == int(sims_props[1]["points"].max())
    for e in uno["eventos"]:
        assert video.P_EVENTO[0] <= e["p_evento"] <= video.P_EVENTO[1]
        assert 0 <= e["p_gana"] <= 1
