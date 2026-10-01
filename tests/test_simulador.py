import numpy as np

from modelo_nba.mercados import mercados
from modelo_nba.simulador import ParametrosSim, simular


def test_no_quedan_empates_y_hay_tiempo_extra_realista():
    s = simular(114.0, 114.0, semilla=7)
    assert not (s.casa == s.visita).any()
    ot = (s.casa_reg == s.visita_reg).mean()
    # La NBA va a OT ~5% de las veces; una normal sola daria ~2.5%.
    assert 0.04 < ot < 0.08


def test_el_mas_fuerte_gana_mas_y_la_media_respeta_la_proyeccion():
    s = simular(120.0, 110.0, semilla=1)
    assert (s.margen > 0).mean() > 0.7
    # El OT suma algo de puntos; el margen medio no se mueve.
    assert abs(s.margen.mean() - 10.0) < 0.5
    assert 229.5 < s.total.mean() < 232.0


def test_lados_del_spread_suman_uno_menos_push():
    s = simular(116.0, 112.0, semilla=3)
    m = mercados(s)
    casa, visita = m["spread_casa"], m["spread_visita"]
    for linea, p in casa.items():
        contraria = f"{-float(linea):+.1f}"
        if contraria not in visita:
            continue
        push = 1 - p - visita[contraria]
        if float(linea) % 1 == 0:
            assert push >= 0
            assert abs(push - (s.margen == -float(linea)).mean()) < 1e-3
        else:
            assert abs(push) < 1e-3


def test_overs_decrecen_con_la_linea():
    m = mercados(simular(112.0, 108.0, semilla=5))
    for clave in ("totales", "team_total_casa", "team_total_visita"):
        vals = [m[clave][k] for k in sorted(m[clave], key=float)]
        assert all(a >= b for a, b in zip(vals, vals[1:]))


def test_primera_mitad_suma_uno():
    pm = mercados(simular(115.0, 110.0, semilla=9))["primera_mitad"]
    assert abs(pm["casa"] + pm["empate"] + pm["visita"] - 1) < 1e-3
    assert pm["casa"] > pm["visita"]


def test_parametros_ida_y_vuelta():
    p = ParametrosSim()
    q = ParametrosSim.de_dict(p.a_dict())
    assert np.allclose(p.cov, q.cov)
    assert q.al_empate == p.al_empate
