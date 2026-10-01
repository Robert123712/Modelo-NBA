import json
from pathlib import Path

import pytest

from modelo_nba import espn

FIX = Path(__file__).parent / "fixtures"


def test_box_desde_summary_real_con_doble_tiempo_extra():
    # OKC 125-124 HOU, 21-oct-2025, dos OT. Respuesta real de ESPN recortada.
    partido, filas = espn.box_desde_summary(json.loads((FIX / "summary_401809243.json").read_text()))
    assert partido["home_abbr"] == "OKC" and partido["away_abbr"] == "HOU"
    assert (partido["home_pts"], partido["away_pts"]) == (125, 124)
    assert partido["periodos"] == 6 and partido["minutos_juego"] == 58
    assert (partido["home_1h"], partido["away_1h"]) == (51, 57)
    assert partido["home_reg"] == partido["away_reg"] == 104
    # Mismo valor que sale de las tablas de hoopR para este partido.
    assert partido["posesiones"] == pytest.approx(117.82)

    durant = next(f for f in filas if f["athlete_display_name"] == "Kevin Durant")
    # El orden de columnas de ESPN no es el de la etiqueta; se lee por clave.
    assert durant["minutes"] == 47 and durant["points"] == 23
    assert (durant["field_goals_made"], durant["field_goals_attempted"]) == (9, 16)
    assert durant["defensive_rebounds"] == 9

    for equipo in (partido["home_id"], partido["away_id"]):
        minutos = sum(f["minutes"] for f in filas if f["team_id"] == equipo)
        assert abs(minutos - 5 * 58) <= 2


def test_roster_con_bajas():
    jugadores = espn.parse_roster(json.loads((FIX / "roster_1_2026.json").read_text()))
    por_nombre = {j["nombre"]: j for j in jugadores}
    assert por_nombre["Jock Landale"]["prob_juega"] == 0.0
    assert por_nombre["Nickeil Alexander-Walker"]["prob_juega"] == 1.0
    assert all(j["estado_conocido"] for j in jugadores)


def _evento(gid, estado="pre"):
    return {
        "id": str(gid),
        "date": "2026-10-21T23:30Z",
        "season": {"year": 2027, "type": 2},
        "competitions": [{
            "neutralSite": False,
            "status": {"type": {"state": estado, "completed": estado == "post"}},
            "competitors": [
                {"homeAway": "home", "team": {"id": "2", "abbreviation": "BOS", "displayName": "Boston Celtics"}},
                {"homeAway": "away", "team": {"id": "18", "abbreviation": "NY", "displayName": "New York Knicks"}},
            ],
        }],
    }


def test_scoreboard():
    juegos = espn.parse_scoreboard({"events": [_evento(401, "pre"), _evento(402, "post")]})
    assert [j["game_id"] for j in juegos] == [401, 402]
    assert juegos[0]["home_abbr"] == "BOS" and juegos[0]["away_id"] == 18
    assert juegos[0]["estado"] == "pre" and juegos[1]["terminado"]


def test_scoreboard_sin_eventos_falla_en_voz_alta():
    with pytest.raises(espn.ErrorESPN):
        espn.parse_scoreboard({"leagues": []})
