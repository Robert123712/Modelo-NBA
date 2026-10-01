import datetime as dt
import json

import pandas as pd

from modelo_nba import datos, diario, espn
from modelo_nba.ratings import Parametros
from modelo_nba.simulador import ParametrosSim

from .test_ratings import _liga


def _juego(gid, casa, visita, estado, hora):
    return {
        "game_id": gid, "starts_at": hora, "season": 2027, "season_type": 2,
        "neutral": False, "estado": estado, "terminado": estado == "post",
        "home_id": casa, "home_abbr": f"C{casa}", "home_nombre": f"Casa {casa}",
        "away_id": visita, "away_abbr": f"V{visita}", "away_nombre": f"Visita {visita}",
    }


def _preparar(monkeypatch, tmp_path, ahora):
    p, j, o, d, plantel, mins = _liga(semilla=2, juegos=600)
    # Tres temporadas atras para que el prior y el corte tengan con que trabajar.
    monkeypatch.setattr(datos, "historia", lambda *a, **k: (p, j))
    cal = pd.DataFrame({
        "season_type": [2, 2], "dia": [dt.date(2026, 10, 20), dt.date(2026, 10, 21)],
        "home_id": [0, 2], "away_id": [5, 3],
    })
    monkeypatch.setattr(datos, "calendario", lambda t: cal)
    monkeypatch.setattr(datos, "novatos", lambda t: pd.DataFrame({"clave": ["novato"], "overall_pick": [2]}))
    monkeypatch.setattr(diario, "cargar_parametros",
                        lambda: (Parametros(lambda_jugador=5), ParametrosSim(simulaciones=4000)))
    juegos = [
        _juego(9001, 0, 1, "pre", "2026-10-21T23:30Z"),
        _juego(9002, 2, 3, "in", "2026-10-21T19:00Z"),
    ]
    monkeypatch.setattr(espn, "scoreboard", lambda f: juegos)

    estrella = max(plantel[0], key=lambda a: o[a] + d[a])

    def roster(tid):
        r = [{"athlete_id": a, "nombre": f"J{a}", "estado": "active", "prob_juega": 1.0,
              "estado_conocido": True} for a in plantel[tid]]
        if tid == 0:
            for x in r:
                if x["athlete_id"] == estrella:
                    x.update(estado="out", prob_juega=0.0)
            r.append({"athlete_id": 99999, "nombre": "Novato", "estado": "active",
                      "prob_juega": 1.0, "estado_conocido": True})
        return r

    monkeypatch.setattr(espn, "roster", roster)
    return estrella


def test_corrida_completa_publica_contrato_y_oficial(monkeypatch, tmp_path):
    ahora = pd.Timestamp("2026-10-21T22:15Z")  # 75 minutos antes del 9001
    estrella = _preparar(monkeypatch, tmp_path, ahora)
    r = diario.predecir(dt.date(2026, 10, 21), ahora, salida=tmp_path)
    assert r["proyectados"] == 1

    env = json.loads((tmp_path / "edgebook-latest.json").read_text())
    assert env["sport"] == "NBA" and env["schema_version"] == "1.1"
    assert env["date_local"] == "2026-10-21"
    (g,) = env["games"]
    assert g["league_game_id"] == g["espn_game_id"] == "9001"
    wp = g["win_probability"]
    assert abs(wp["home"] + wp["away"] - 1) < 1e-6
    assert g["pick"]["side"] == ("home" if wp["home"] >= 0.5 else "away")
    assert 150 < g["total_points"] < 300
    assert g["spread"]["home"] == -g["spread"]["away"]
    assert all(len(f["label"]) <= 40 for f in g["key_factors"])

    detalle = json.loads((tmp_path / "latest.json").read_text())["games"][0]
    nombres = [x["jugador"] for x in detalle["rotacion"]["home"]]
    assert "Novato" in nombres  # el pick 2 entra con minutos de novato
    assert f"J{estrella}" not in nombres  # el "out" no juega
    assert abs(sum(x["minutos"] for x in detalle["rotacion"]["home"]) - 240) < 3
    assert {"spread_casa", "totales", "team_total_casa", "primera_mitad"} <= set(detalle["mercados"])

    oficiales = json.loads((tmp_path / "oficiales" / "2026-10-21.json").read_text())
    assert oficiales["9001"]["tardia"] is False

    # Una corrida a 45 minutos no reemplaza la oficial, y el partido sigue
    # publicado aunque ya no este en "pre".
    tarde = pd.Timestamp("2026-10-21T22:45Z")
    diario.predecir(dt.date(2026, 10, 21), tarde, salida=tmp_path)
    oficiales2 = json.loads((tmp_path / "oficiales" / "2026-10-21.json").read_text())
    assert oficiales2["9001"]["generated_at"] == oficiales["9001"]["generated_at"]
