import pandas as pd

from modelo_nba import tendencias as td


def _tabla():
    """Seis defensas; la 3 regala rebotes a los guardias que reparten (PG)."""
    filas = []
    inicio = pd.Timestamp("2025-11-01", tz="UTC")
    for g in range(120):
        rival = g % 6 + 1
        for a, posicion, ast, reb in ((10, "G", 9.0, 4.0), (11, "G", 2.0, 3.0),
                                      (12, "F", 2.0, 9.0), (13, "F", 2.0, 4.0), (14, "C", 1.0, 11.0)):
            if a == 10 and rival == 3:
                reb = 12.0
            filas.append(dict(
                game_id=g, athlete_id=a, team_id=9, rival=rival, posicion=posicion,
                fecha=inicio + pd.Timedelta(days=g), season=2026, season_type=2, pos=70.0,
                points=15.0, reb=reb, assists=ast, blocks=0.5,
                three_point_field_goals_made=2.0,
            ))
    return pd.DataFrame(filas)


def test_cinco_posiciones_con_los_minutos_partidos():
    t = _tabla()
    pos5 = td.posiciones5(t, t.fecha.max() + pd.Timedelta(days=1))
    assert pos5.to_dict() == {10: "PG", 11: "SG", 12: "PF", 13: "SF", 14: "C"}


def test_ranking_y_linea_con_su_jugador():
    t = _tabla()
    corte = t.fecha.max() + pd.Timedelta(days=1)
    R = td.rankings(t, corte, 2026, td.posiciones5(t, corte))
    assert R["temporada"]["nombre"] == "Temporada"
    assert R["temporada"]["lugar"].at[(3, "PG"), "reb"] == 1
    casa = {"abbr": "DEF", "team_id": 3, "rotacion": []}
    visita = {"abbr": "ATQ", "team_id": 9, "rotacion": [(10, "PG"), (99, "PG"), (14, "C")]}
    out = td.del_partido(R, casa, visita)
    # La linea va al PG con mas minutos (10), no al otro.
    assert 99 not in out
    reb = [x for x in out[10] if x["stat"] == "rebotes"]
    assert reb and reb[0]["lugar"] == 1 and reb[0]["defensa"] == "DEF" and reb[0]["posicion"] == "PG"
    assert len(out[10]) <= td.POR_JUGADOR
