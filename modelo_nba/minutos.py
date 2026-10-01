"""Minutos proyectados de cada jugador disponible.

La base es un promedio exponencial de los minutos de sus partidos recientes en
los que estaba disponible (cualquier equipo: un traspaso conserva el rol hasta
que el nuevo equipo diga otra cosa). Un DNP por decision del coach cuenta como
cero minutos, porque es su rol; un DNP por lesion o ausencia no cuenta, porque
no dice nada de su rol.

Luego se reparten los minutos del partido (240 en reglamento) entre los
disponibles, proporcional a esa base y con tope, que es justamente como se
redistribuyen los minutos de una baja.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

VIDA_MEDIA_PARTIDOS = 6.0  # se ajusta en el backtest
TOPE_MINUTOS = 40.0
# Minutos base de alguien sin historial (debut). Entra a la rotacion solo si
# faltan cuerpos.
MINUTOS_SIN_HISTORIAL = 6.0


def no_disponible(did_not_play: pd.Series, reason: pd.Series) -> pd.Series:
    """DNP que no fue decision del coach: lesion, enfermedad, suspension..."""
    return did_not_play & ~reason.str.upper().str.startswith("COACH")


def _ewm(serie: pd.Series) -> pd.Series:
    alpha = 1 - 0.5 ** (1 / VIDA_MEDIA_PARTIDOS)
    return serie.ewm(alpha=alpha, adjust=True).mean()


def con_minutos_previos(jugadores: pd.DataFrame, partidos: pd.DataFrame) -> pd.DataFrame:
    """Agrega `m_base`: la base de minutos ANTES de cada partido.

    Se calcula una vez para todo el historico; el backtest la lee sin fuga
    porque cada fila solo ve partidos anteriores.

    Para temporada regular la base ignora los playoffs: ahi las estrellas
    juegan 40 minutos, y arrastrar eso al arranque de la temporada siguiente
    sobreestima su rol. Para un partido de playoffs si cuentan, porque la
    rotacion se cierra.
    """
    info = partidos.set_index("game_id")[["fecha", "season_type"]]
    j = jugadores.join(info, on="game_id")
    j["disponible"] = ~no_disponible(j.did_not_play, j.reason)
    j = j.sort_values(["athlete_id", "fecha"])
    disp = j[j.disponible].copy()
    disp["m_todos"] = disp.groupby("athlete_id").minutes.transform(_ewm)
    disp["m_todos"] = disp.groupby("athlete_id").m_todos.shift(1)
    reg = disp[disp.season_type != 3].copy()
    reg["m_post_reg"] = reg.groupby("athlete_id").minutes.transform(_ewm)
    disp = disp.merge(reg[["game_id", "athlete_id", "m_post_reg"]], on=["game_id", "athlete_id"], how="left")
    # Ultimo valor de temporada regular visto ANTES de cada fila.
    disp["m_reg"] = disp.groupby("athlete_id").m_post_reg.transform(lambda s: s.shift(1).ffill())
    disp["m_base"] = np.where(disp.season_type == 3, disp.m_todos, disp.m_reg)
    j = j.merge(disp[["game_id", "athlete_id", "m_base"]], on=["game_id", "athlete_id"], how="left")
    return j


def minutos_actuales(jugadores: pd.DataFrame, partidos: pd.DataFrame, antes_de, playoffs: bool = False) -> pd.Series:
    """Base de minutos de cada jugador con todo lo jugado antes de `antes_de`."""
    info = partidos.set_index("game_id")[["fecha", "season_type"]]
    j = jugadores.join(info, on="game_id")
    j = j[(j.fecha < antes_de) & ~no_disponible(j.did_not_play, j.reason)]
    if not playoffs:
        j = j[j.season_type != 3]
    j = j.sort_values(["athlete_id", "fecha"])
    return j.groupby("athlete_id").minutes.agg(lambda s: _ewm(s).iloc[-1])


MODO_REPARTO = "resta"


def repartir(base: dict[int, float], minutos_partido: float = 48.0, modo: str | None = None) -> dict[int, float]:
    """Lleva la base a 5 * minutos_partido, con tope por jugador.

    Si sobran minutos (roster profundo), se le resta lo mismo a todos y los del
    fondo de la banca se quedan en cero: asi se cae una rotacion real, donde el
    titular no pierde minutos porque haya un decimo quinto jugador sano. Si
    faltan (bajas), se reparten proporcional a la base.
    """
    modo = modo or MODO_REPARTO
    total = 5 * minutos_partido
    ids = list(base)
    b = np.array([base[a] if base[a] == base[a] else MINUTOS_SIN_HISTORIAL for a in ids], float)
    b = np.clip(b, 0.0, None)
    if b.sum() <= 0:
        b = np.ones_like(b)
    if modo == "resta" and b.sum() > total:
        # t tal que sum(max(0, b - t)) = total; b ordenado de mayor a menor.
        orden = np.sort(b)[::-1]
        acum = np.cumsum(orden)
        k = np.arange(1, len(orden) + 1)
        t_k = (acum - total) / k
        validos = t_k < orden
        t = t_k[validos][-1]
        b = np.maximum(b - t, 0.0)
    m = np.zeros_like(b)
    libres = np.ones(len(b), bool)
    restante = total
    # Al topar a uno, lo que sobra se reparte entre los demas; a lo sumo unas
    # cuantas vueltas porque cada una fija al menos a un jugador.
    for _ in range(len(b)):
        escala = restante / b[libres].sum() if b[libres].sum() > 0 else 0.0
        m[libres] = b[libres] * escala
        topados = libres & (m > TOPE_MINUTOS)
        if not topados.any():
            break
        m[topados] = TOPE_MINUTOS
        libres &= ~topados
        restante = total - m[~libres].sum()
    return dict(zip(ids, m.tolist()))
