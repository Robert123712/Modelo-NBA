"""Del rating de los que juegan a los puntos esperados de cada equipo."""

from __future__ import annotations

from dataclasses import dataclass

from .ratings import Ratings


@dataclass
class Esperado:
    ortg_casa: float
    ortg_visita: float
    pace: float  # posesiones en 48 minutos
    puntos_casa: float  # en reglamento
    puntos_visita: float
    # Aporte de cada pieza al margen esperado de la casa, en puntos. Es la
    # materia prima de los factores que se explican en pantalla.
    desglose: dict[str, float]


def _suma(R: Ratings, rotacion: dict[int, float], minutos_partido: float):
    o = d = 0.0
    for a, m in rotacion.items():
        ro, rd = R.jugador(a)
        s = m / minutos_partido
        o += s * ro
        d += s * rd
    return o, d


def esperar(
    R: Ratings,
    temporada: int,
    casa: int,
    visita: int,
    rot_casa: dict[int, float],
    rot_visita: dict[int, float],
    neutral: bool = False,
    b2b_casa: bool = False,
    b2b_visita: bool = False,
) -> Esperado:
    mu = R.mu_actual(temporada)
    loc = 0.0 if neutral else R.localia
    o_c, d_c = _suma(R, rot_casa, 48.0)
    o_v, d_v = _suma(R, rot_visita, 48.0)
    ctx = R.contexto
    b2b_c = ctx["b2b_ofensiva"] * b2b_casa + ctx["b2b_defensa"] * b2b_visita
    b2b_v = ctx["b2b_ofensiva"] * b2b_visita + ctx["b2b_defensa"] * b2b_casa
    # Efecto de sistema de cada equipo (0 si el modelo no lo usa).
    o_c += R.equipo_o.get(casa, 0.0)
    d_c += R.equipo_d.get(casa, 0.0)
    o_v += R.equipo_o.get(visita, 0.0)
    d_v += R.equipo_d.get(visita, 0.0)
    ortg_c = mu + loc + o_c - d_v + b2b_c
    ortg_v = mu - loc + o_v - d_c + b2b_v
    pace = (
        R.pace_actual(temporada)
        + R.pace_equipo.get(casa, 0.0)
        + R.pace_equipo.get(visita, 0.0)
    )
    k = pace / 100
    return Esperado(
        ortg_casa=ortg_c,
        ortg_visita=ortg_v,
        pace=pace,
        puntos_casa=ortg_c * k,
        puntos_visita=ortg_v * k,
        desglose={
            "localia": 2 * loc * k,
            "ofensiva_casa": o_c * k,
            "defensa_casa": d_c * k,
            "ofensiva_visita": -o_v * k,
            "defensa_visita": -d_v * k,
            "descanso": (b2b_c - b2b_v) * k,
        },
    )
