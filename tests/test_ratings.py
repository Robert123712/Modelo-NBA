import numpy as np
import pandas as pd

from modelo_nba.minutos import repartir
from modelo_nba.proyeccion import esperar
from modelo_nba.ratings import Parametros, ajustar


def _liga(semilla=0, equipos=10, por_equipo=9, juegos=900):
    """Liga sintetica con ratings verdaderos conocidos."""
    rng = np.random.default_rng(semilla)
    n = equipos * por_equipo
    o = rng.normal(0, 1.5, n)
    d = rng.normal(0, 1.5, n)
    plantel = {t: list(range(t * por_equipo, (t + 1) * por_equipo)) for t in range(equipos)}
    mins = np.array([36, 34, 32, 30, 28, 24, 20, 20, 16], float)
    inicio = pd.Timestamp("2025-10-20", tz="UTC")
    partidos, jugadores = [], []
    for g in range(juegos):
        c, v = rng.choice(equipos, 2, replace=False)
        pos = rng.normal(100, 4)
        def ortg(of, de, signo):
            return (112 + 1.0 * signo
                    + sum(m / 48 * o[a] for a, m in zip(plantel[of], mins))
                    - sum(m / 48 * d[a] for a, m in zip(plantel[de], mins)))
        pc = ortg(c, v, 1) * pos / 100 + rng.normal(0, 8)
        pv = ortg(v, c, -1) * pos / 100 + rng.normal(0, 8)
        fecha = inicio + pd.Timedelta(hours=8 * g)
        partidos.append(dict(
            game_id=g, season=2026, season_type=2, fecha=fecha, home_id=c, away_id=v,
            neutral=False, home_pts=pc, away_pts=pv, posesiones=pos, minutos_juego=48,
            periodos=4, dia=fecha.tz_convert("America/New_York").date(),
        ))
        for t in (c, v):
            for a, m in zip(plantel[t], mins):
                fila = dict(game_id=g, team_id=t, athlete_id=a, athlete_display_name=str(a),
                            minutes=m, did_not_play=False, reason="")
                for st in ("points", "field_goals_attempted", "three_point_field_goals_attempted",
                           "free_throws_attempted", "assists", "turnovers", "offensive_rebounds",
                           "defensive_rebounds", "steals", "blocks", "fouls"):
                    fila[st] = m / 4
                jugadores.append(fila)
    return pd.DataFrame(partidos), pd.DataFrame(jugadores), o, d, plantel, mins


def test_recupera_la_fuerza_relativa_de_los_equipos():
    p, j, o, d, plantel, mins = _liga()
    R = ajustar(p, j, pd.Timestamp("2027-01-01", tz="UTC"), Parametros(vida_media=10_000, lambda_jugador=5))
    verdad, estimado = [], []
    for t, ids in plantel.items():
        verdad.append(sum(m / 48 * (o[a] + d[a]) for a, m in zip(ids, mins)))
        estimado.append(sum(m / 48 * (R.ofensiva[a] + R.defensa[a]) for a, m in zip(ids, mins)))
    assert np.corrcoef(verdad, estimado)[0, 1] > 0.95
    assert abs(R.localia - 1.0) < 0.6
    assert abs(R.mu_actual(2026) - 112) < 1.5


def test_proyeccion_sube_con_la_localia_y_baja_sin_el_mejor():
    p, j, o, d, plantel, mins = _liga(semilla=1)
    R = ajustar(p, j, pd.Timestamp("2027-01-01", tz="UTC"), Parametros(vida_media=10_000, lambda_jugador=5))
    rot = {t: repartir(dict(zip(ids, mins))) for t, ids in plantel.items()}
    e = esperar(R, 2026, 0, 1, rot[0], rot[1])
    e_neutral = esperar(R, 2026, 0, 1, rot[0], rot[1], neutral=True)
    assert e.puntos_casa - e.puntos_visita > e_neutral.puntos_casa - e_neutral.puntos_visita

    mejor = max(plantel[0], key=lambda a: R.ofensiva[a] + R.defensa[a])
    sin_mejor = repartir({a: m for a, m in zip(plantel[0], mins) if a != mejor})
    e_baja = esperar(R, 2026, 0, 1, sin_mejor, rot[1])
    assert e_baja.puntos_casa - e_baja.puntos_visita < e.puntos_casa - e.puntos_visita
