import numpy as np
import pandas as pd

from modelo_nba.emitir import factor_modelos
from modelo_nba.ensamble import Arbitro, _convexos, grupo
from modelo_nba.motores import elo

from .test_ratings import _liga


def test_elo_el_que_gana_sube_y_suma_cero():
    p, *_ = _liga(semilla=3, juegos=300)
    tabla, estado = elo.historial(p)
    assert len(tabla) == len(p)
    assert abs(np.mean([e for e, _ in estado.values()]) - elo.MEDIA) < 1e-6
    # El que mas gano termina con mas Elo.
    gana = pd.concat([
        p.assign(t=p.home_id, w=p.home_pts > p.away_pts),
        p.assign(t=p.away_id, w=p.away_pts > p.home_pts),
    ]).groupby("t").w.mean()
    assert estado[gana.idxmax()][0] > estado[gana.idxmin()][0]


def test_elo_regresa_a_la_media_entre_temporadas():
    estado = {1: [1605.0, 2026], 2: [1405.0, 2026]}
    misma = elo.predecir(estado, 1, 2, 2026, neutral=True)
    nueva = elo.predecir(estado, 1, 2, 2027, neutral=True)
    assert 0 < nueva < misma


def test_pesos_convexos_encuentran_al_motor_bueno():
    rng = np.random.default_rng(0)
    verdad = rng.normal(0, 10, 2000)
    bueno = verdad + rng.normal(0, 2, 2000)
    malo = rng.normal(0, 10, 2000)
    w, _ = _convexos(np.column_stack([bueno, malo]), verdad + rng.normal(0, 1, 2000))
    assert w[0] > 0.9 and abs(w.sum() - 1) < 1e-9 and (w >= 0).all()


def test_arbitro_reescala_si_falta_un_motor():
    a = Arbitro(
        {"global": {"jugadores": 0.5, "elo": 0.25, "equipos": 0.25, "factores": 0.0}},
        {"global": {"jugadores": 1.0}}, {"global": 0.0}, {"global": 0.0},
    )
    c = a.combinar({"jugadores": 6.0, "elo": float("nan"), "equipos": 0.0, "factores": 9.0},
                   {"jugadores": 220.0}, jugados=40, bajas=0.0)
    assert abs(c["margen"] - (6.0 * 2 / 3)) < 1e-9
    assert c["total"] == 220.0
    assert grupo(5, 0.2) == "inicio|con_bajas" and grupo(40, 0.0) == "madura|normal"


def test_factor_modelos_cuenta_y_explica():
    juego = {"home_abbr": "BOS", "away_abbr": "NY"}
    f = factor_modelos(juego, {"jugadores": 6.1, "elo": 4.0, "equipos": 5.2, "factores": -0.5}, "home")
    assert f["favors"] == "home" and f["supports_pick"]
    assert "3 de 4 modelos ven ganar a BOS" in f["detail"]
    empate = factor_modelos(juego, {"jugadores": 2.0, "elo": 1.0, "equipos": -1.0, "factores": -3.0}, "home")
    assert empate["favors"] is None and "2-2" in empate["detail"]
