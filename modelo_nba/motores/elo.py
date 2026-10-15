"""Motor 2: Elo con margen de victoria.

No sabe nada de jugadores ni de estadisticas: solo quien le gano a quien, por
cuanto y donde. Por eso es independiente de los otros motores, y por eso
reacciona a rachas que el modelo de jugadores tarda en ver (un equipo que
cambio de sistema, un entrenador nuevo).

Es la version de FiveThirtyEight para la NBA:
  - la ganancia por partido crece con el margen, pero menos que lineal, y se
    descuenta cuando el favorito gana por mucho (si no, los favoritos inflan
    su Elo ganando como deben);
  - al cambiar de temporada cada equipo regresa un 25% hacia la media;
  - 28 puntos de Elo equivalen a 1 punto de margen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MEDIA = 1505.0
ELO_POR_PUNTO = 28.0


@dataclass
class ParametrosElo:
    k: float = 25.0  # afinado en 2023-24 y 2024-25
    localia: float = 60.0  # puntos de Elo (~2.1 de margen)
    regreso_temporada: float = 0.25


def _multiplicador(margen_ganador: float, dif_elo_ganador: float) -> float:
    return ((abs(margen_ganador) + 3) ** 0.8) / (7.5 + 0.006 * dif_elo_ganador)


def historial(partidos: pd.DataFrame, params: ParametrosElo | None = None):
    """Elo de cada equipo ANTES de cada partido, y el estado al final.

    Devuelve (DataFrame[game_id, elo_casa, elo_visita, margen_elo], estado),
    donde estado = {team_id: (elo, ultima_temporada)}.
    """
    params = params or ParametrosElo()
    estado: dict[int, list] = {}
    filas = []
    for p in partidos.sort_values(["fecha", "game_id"]).itertuples():
        elos = []
        for t in (p.home_id, p.away_id):
            if t not in estado:
                estado[t] = [MEDIA, p.season]
            elif estado[t][1] != p.season:
                e = estado[t][0]
                estado[t] = [e + params.regreso_temporada * (MEDIA - e), p.season]
            elos.append(estado[t][0])
        loc = 0.0 if p.neutral else params.localia
        dif = elos[0] + loc - elos[1]
        filas.append((p.game_id, elos[0], elos[1], dif / ELO_POR_PUNTO))

        margen = p.home_pts - p.away_pts
        esperado = 1 / (1 + 10 ** (-dif / 400))
        real = 1.0 if margen > 0 else 0.0
        dif_ganador = dif if margen > 0 else -dif
        cambio = params.k * _multiplicador(margen, dif_ganador) * (real - esperado)
        estado[p.home_id][0] += cambio
        estado[p.away_id][0] -= cambio

    tabla = pd.DataFrame(filas, columns=["game_id", "elo_casa", "elo_visita", "margen_elo"])
    return tabla, estado


def predecir(estado: dict, casa: int, visita: int, temporada: int, neutral: bool,
             params: ParametrosElo | None = None) -> float:
    """Margen esperado de la casa para un partido futuro."""
    params = params or ParametrosElo()

    def elo(t):
        if t not in estado:
            return MEDIA
        e, ultima = estado[t]
        if ultima != temporada:
            e = e + params.regreso_temporada * (MEDIA - e)
        return e

    loc = 0.0 if neutral else params.localia
    return (elo(casa) + loc - elo(visita)) / ELO_POR_PUNTO
