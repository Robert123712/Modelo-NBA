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

# Memoria corta: cuando cambia el rol de alguien, lo reciente manda. En el
# estudio de minutos (docs/MINUTOS.md) 2 partidos fue el mejor valor en 2024-25
# y en 2025-26; con 6, la racha de los ultimos 3 partidos seguia explicando
# 1.3 minutos de error por cada 5 de diferencia.
VIDA_MEDIA_PARTIDOS = 2.0
# El modelo del marcador (spread y total) y el arbitro se quedan con 6: en
# 2025-26 la memoria corta y las correcciones no le cambiaron el error (margen
# 11.19 contra 11.19, total 14.82 contra 14.80). Lo nuevo es solo para props.
VIDA_MEDIA_MARCADOR = 6.0
# Arranque de temporada: la base parte del promedio de la temporada pasada y
# pasa a lo reciente conforme juega (peso de lo reciente = k / (k + K), con k
# partidos de esta temporada). Sin esto, los ultimos 6 partidos del ano pasado
# mandaban: Cody Williams en un Utah que tanqueaba (34 de base, 21 de
# promedio) o Edwards descansando (32.7 contra 35). Medido en 2024-26: K=0.5
# baja el error de los 3 primeros partidos de 5.79 a 5.63 minutos y el de los
# que cambiaron de equipo de 6.84 a 6.56, sin empeorar el resto (5.006 ->
# 5.004); K mas grande arrastra el promedio viejo de mas.
K_ARRANQUE = 0.5
TOPE_MINUTOS = 40.0
# Minutos base de alguien sin historial (debut). Entra a la rotacion solo si
# faltan cuerpos.
MINUTOS_SIN_HISTORIAL = 6.0
# Solo los 11 de mayor base entran al reparto. El roster de ESPN trae 15-18
# (two-way incluidos) y cada uno de mas le restaba minutos a los titulares.
# Medido en 2024-26 contra el box score: tope 11, error 5.01 minutos; sin tope,
# 5.07; con 9 o 10, las estrellas se sobreestiman.
MAX_JUGADORES = 11


def no_disponible(did_not_play: pd.Series, reason: pd.Series) -> pd.Series:
    """DNP que no fue decision del coach: lesion, enfermedad, suspension..."""
    return did_not_play & ~reason.str.upper().str.startswith("COACH")


def _ewm(serie: pd.Series, vida: float | None = None) -> pd.Series:
    alpha = 1 - 0.5 ** (1 / (vida or VIDA_MEDIA_PARTIDOS))
    return serie.ewm(alpha=alpha, adjust=True).mean()


def con_minutos_previos(jugadores: pd.DataFrame, partidos: pd.DataFrame, vida: float | None = None) -> pd.DataFrame:
    """Agrega `m_base`: la base de minutos ANTES de cada partido.

    Se calcula una vez para todo el historico; el backtest la lee sin fuga
    porque cada fila solo ve partidos anteriores.

    Para temporada regular la base ignora los playoffs: ahi las estrellas
    juegan 40 minutos, y arrastrar eso al arranque de la temporada siguiente
    sobreestima su rol. Para un partido de playoffs si cuentan, porque la
    rotacion se cierra.
    """
    info = partidos.set_index("game_id")[["fecha", "season_type", "season"]]
    j = jugadores.join(info, on="game_id")
    j["disponible"] = ~no_disponible(j.did_not_play, j.reason)
    j = j.sort_values(["athlete_id", "fecha"])
    disp = j[j.disponible].copy()
    ewm = lambda x: _ewm(x, vida)  # noqa: E731
    disp["m_todos"] = disp.groupby("athlete_id").minutes.transform(ewm)
    disp["m_todos"] = disp.groupby("athlete_id").m_todos.shift(1)
    reg = disp[disp.season_type != 3].copy()
    reg["m_post_reg"] = reg.groupby("athlete_id").minutes.transform(ewm)
    disp = disp.merge(reg[["game_id", "athlete_id", "m_post_reg"]], on=["game_id", "athlete_id"], how="left")
    # Ultimo valor de temporada regular visto ANTES de cada fila.
    disp["m_reg"] = disp.groupby("athlete_id").m_post_reg.transform(lambda s: s.shift(1).ffill())
    disp["m_base"] = np.where(disp.season_type == 3, disp.m_todos, disp.m_reg)
    disp = _con_arranque(disp)
    j = j.merge(disp[["game_id", "athlete_id", "m_base"]], on=["game_id", "athlete_id"], how="left")
    return j


def _mezcla_arranque(base, prom_pasada, k):
    """La base con el promedio de la temporada pasada, segun cuanto lleva jugado."""
    w = k / (k + K_ARRANQUE)
    return np.where(pd.notna(prom_pasada) & pd.notna(base), w * base + (1 - w) * prom_pasada, base)


def _con_arranque(disp: pd.DataFrame) -> pd.DataFrame:
    """`m_base` de temporada regular con el arranque de temporada (ver K_ARRANQUE)."""
    reg = disp.season_type != 3
    prom = disp[reg].groupby(["athlete_id", "season"]).minutes.mean().rename("prom_pasada").reset_index()
    prom["season"] += 1
    disp = disp.merge(prom, on=["athlete_id", "season"], how="left").sort_values(["athlete_id", "fecha"])
    disp["k_temp"] = disp[disp.season_type != 3].groupby(["athlete_id", "season"]).cumcount()
    mezcla = _mezcla_arranque(disp.m_base, disp.prom_pasada, disp.k_temp)
    disp["m_base"] = np.where(disp.season_type != 3, mezcla, disp.m_base)
    return disp.drop(columns=["prom_pasada", "k_temp"])


def minutos_actuales(jugadores: pd.DataFrame, partidos: pd.DataFrame, antes_de, playoffs: bool = False,
                     temporada: int | None = None, vida: float | None = None) -> pd.Series:
    """Base de minutos de cada jugador con todo lo jugado antes de `antes_de`.

    Con `temporada` (y fuera de playoffs) se aplica el arranque de temporada:
    ver K_ARRANQUE. `vida` cambia la memoria (por omision VIDA_MEDIA_PARTIDOS).
    """
    info = partidos.set_index("game_id")[["fecha", "season_type", "season"]]
    j = jugadores.join(info, on="game_id")
    j = j[(j.fecha < antes_de) & ~no_disponible(j.did_not_play, j.reason)]
    if not playoffs:
        j = j[j.season_type != 3]
    j = j.sort_values(["athlete_id", "fecha"])
    base = j.groupby("athlete_id").minutes.agg(lambda s: _ewm(s, vida).iloc[-1])
    if temporada is None or playoffs:
        return base
    k = j[j.season == temporada].groupby("athlete_id").size().reindex(base.index).fillna(0)
    prom = j[j.season == temporada - 1].groupby("athlete_id").minutes.mean().reindex(base.index)
    return pd.Series(_mezcla_arranque(base.values, prom.values, k.values), index=base.index)


def promedio_referencia(jugadores: pd.DataFrame, partidos: pd.DataFrame, antes_de, temporada: int,
                        minimo: int = 5) -> pd.Series:
    """Minutos por partido contra los que se revisa la proyeccion: los de esta
    temporada si ya lleva `minimo` partidos, si no los de la pasada."""
    info = partidos.set_index("game_id")[["fecha", "season_type", "season"]]
    j = jugadores.join(info, on="game_id")
    j = j[(j.fecha < antes_de) & (j.season_type != 3) & ~no_disponible(j.did_not_play, j.reason)]
    actual = j[j.season == temporada].groupby("athlete_id").minutes.agg(["mean", "size"])
    pasada = j[j.season == temporada - 1].groupby("athlete_id").minutes.mean()
    ref = pasada.copy()
    usar = actual[actual["size"] >= minimo]["mean"]
    ref.loc[usar.index] = usar
    return ref


# --- Correcciones por contexto (docs/MINUTOS.md) -----------------------------
# Lo que la base no ve y en el estudio movio los minutos en 2024-25 y 2025-26.
# Se suman a la base antes del reparto, asi que el equipo sigue sumando 240.
# Los coeficientes se ajustaron en 2024-25 con todo el proceso (base, reparto
# y paliza del simulador) y se probaron a ciegas en 2025-26.
CORRECCION = {
    "titular": 2.4,          # fue titular en su partido anterior
    "regreso": -2.6,         # primer partido tras perderse 3+ de su equipo
    "traspaso": -3.8,        # primer partido con su equipo nuevo
    "arranque": -1.8,        # primeros 5 partidos de la temporada
    "veterano_b2b": -1.2,    # 31+ anos y su equipo jugo ayer
    "bajas": 0.29,           # por cada 10 minutos habituales que faltan hoy
    "bajas_titular": -0.63,  # ... y si es titular, esto ademas
    "faltas": -0.16,         # por cada falta por 36 minutos arriba de 3
    "encoge": -0.1,          # acerca la base a 25 minutos
}
PARTIDOS_REGRESO = 3
PARTIDOS_ARRANQUE = 5
EDAD_VETERANO = 31.0
VENTANA_FALTAS = 15


def _juegos_entre(fechas_equipo: np.ndarray, desde, hasta) -> np.ndarray:
    """Partidos del equipo con fecha en (desde, hasta); fechas ordenadas."""
    return (np.searchsorted(fechas_equipo, hasta, side="left")
            - np.searchsorted(fechas_equipo, desde, side="right"))


def _fechas_equipos(partidos: pd.DataFrame) -> dict[int, np.ndarray]:
    t = pd.concat([partidos[["fecha", "home_id"]].rename(columns={"home_id": "t"}),
                   partidos[["fecha", "away_id"]].rename(columns={"away_id": "t"})])
    return {int(k): np.sort(x.fecha.values) for k, x in t.groupby("t")}


def con_rasgos(jm: pd.DataFrame, partidos: pd.DataFrame, nacimientos: dict | None = None) -> pd.DataFrame:
    """Rasgos previos de cada fila de `con_minutos_previos` (para el backtest).

    Todo con partidos anteriores: titular en su partido anterior, partidos de su
    equipo que se perdio justo antes, traspaso, partidos de la temporada, faltas
    por 36 y si es veterano. `bajas_eq`: minutos habituales de los companeros
    que faltan (jugaron en los ultimos 15 dias).
    """
    jm = jm.sort_values(["athlete_id", "fecha"]).copy()
    d = jm[jm.disponible].copy()
    g = d.groupby("athlete_id")
    d["titular_prev"] = g.starter.shift(1).eq(True)
    d["fecha_prev"] = g.fecha.shift(1)
    d["equipo_prev"] = g.team_id.shift(1)
    d["k_temp"] = d.groupby(["athlete_id", "season", "season_type"]).cumcount()
    jugo = d.minutes > 0
    f = d.fouls.where(jugo, 0.0).groupby(d.athlete_id).transform(
        lambda s: s.shift(1).rolling(VENTANA_FALTAS, min_periods=5).sum())
    m = d.minutes.where(jugo, 0.0).groupby(d.athlete_id).transform(
        lambda s: s.shift(1).rolling(VENTANA_FALTAS, min_periods=5).sum())
    d["faltas36"] = (f / m.where(m > 0) * 36).fillna(3.0)
    fe = _fechas_equipos(partidos)
    fuera = np.zeros(len(d), int)
    for t, idx in d.groupby("team_id").indices.items():
        x = d.iloc[idx]
        ok = x.fecha_prev.notna().values
        n = np.zeros(len(x), int)
        n[ok] = _juegos_entre(fe[int(t)], x.fecha_prev.values[ok], x.fecha.values[ok])
        fuera[idx] = n
    d["fuera"] = fuera
    d["traspaso"] = d.equipo_prev.notna() & (d.equipo_prev != d.team_id)
    d["veterano"] = _veterano(d.athlete_id, d.fecha, nacimientos)
    # Bajas: los no disponibles que jugaron hace poco, con su ultima base.
    jm["habitual"] = jm.groupby("athlete_id").m_base.ffill()
    ult = jm.fecha.where(jm.disponible).groupby(jm.athlete_id).transform(lambda s: s.shift(1).ffill())
    falta = ~jm.disponible & ((jm.fecha - ult) <= pd.Timedelta(days=15)) & jm.habitual.notna()
    bajas = jm[falta].groupby(["game_id", "team_id"]).habitual.sum().rename("bajas_eq")
    d = d.join(bajas, on=["game_id", "team_id"])
    d["bajas_eq"] = d.bajas_eq.fillna(0.0)
    cols = ["titular_prev", "fuera", "traspaso", "k_temp", "faltas36", "veterano", "bajas_eq"]
    return jm.drop(columns="habitual").join(d[cols])


def _veterano(athlete_id: pd.Series, fecha: pd.Series, nacimientos: dict | None) -> np.ndarray:
    if not nacimientos:
        return np.zeros(len(athlete_id), bool)
    nac = pd.to_datetime(athlete_id.map(nacimientos), utc=True, errors="coerce")
    edad = (pd.to_datetime(fecha, utc=True) - nac).dt.days / 365.25
    return (edad >= EDAD_VETERANO).fillna(False).values


def rasgos_actuales(jugadores: pd.DataFrame, partidos: pd.DataFrame, antes_de, temporada: int) -> pd.DataFrame:
    """Los mismos rasgos que `con_rasgos`, para la corrida de hoy (sin `fuera`,
    `veterano` ni `bajas_eq`, que dependen del equipo y el roster de hoy)."""
    info = partidos.set_index("game_id")[["fecha", "season_type", "season"]]
    j = jugadores.join(info, on="game_id")
    j = j[(j.fecha < antes_de) & ~no_disponible(j.did_not_play, j.reason)].sort_values(["athlete_id", "fecha"])
    for c, v in (("starter", False), ("fouls", np.nan)):
        if c not in j:
            j[c] = v
    g = j.groupby("athlete_id")
    ult = g.tail(1).set_index("athlete_id")
    out = pd.DataFrame({
        "titular_prev": ult.starter.eq(True),
        "fecha_prev": ult.fecha,
        "equipo_prev": ult.team_id,
    })
    reg = j[(j.season == temporada) & (j.season_type == 2)]
    out["k_temp"] = reg.groupby("athlete_id").size().reindex(out.index).fillna(0).astype(int)
    ult15 = j[j.minutes > 0].groupby("athlete_id").tail(VENTANA_FALTAS)
    s = ult15.groupby("athlete_id")[["fouls", "minutes"]].sum()
    n = ult15.groupby("athlete_id").size()
    f36 = (s.fouls / s.minutes * 36).where(n >= 5)
    out["faltas36"] = f36.reindex(out.index).fillna(3.0)
    return out


def juegos_fuera(partidos: pd.DataFrame, team_id: int, fecha_prev, antes_de) -> int:
    """Partidos de su equipo desde su ultimo partido disponible hasta hoy."""
    fe = _fechas_equipos(partidos).get(int(team_id))
    if fe is None or fecha_prev is None or pd.isna(fecha_prev):
        return 0
    utc = lambda x: pd.Timestamp(x).tz_convert("UTC").tz_localize(None).to_datetime64()  # noqa: E731
    return int(_juegos_entre(fe, utc(fecha_prev), utc(antes_de)))


RASGOS = ["titular_prev", "fuera", "traspaso", "k_temp", "faltas36", "veterano"]


def corregir(base: dict[int, float], rasgos: dict[int, dict], b2b: bool, bajas: float,
             coef: dict | None = None) -> dict[int, float]:
    """Base corregida por contexto (ver CORRECCION). Sin rasgos, queda igual."""
    c = coef or CORRECCION
    out = {}
    for a, b in base.items():
        r = rasgos.get(a)
        if r is None or b != b:
            out[a] = b
            continue
        t = float(bool(r.get("titular_prev", False)))
        ajuste = (
            c["titular"] * t
            + c["regreso"] * (r.get("fuera", 0) >= PARTIDOS_REGRESO and not r.get("traspaso", False))
            + c["traspaso"] * bool(r.get("traspaso", False))
            + c["arranque"] * (r.get("k_temp", 99) < PARTIDOS_ARRANQUE)
            + c["veterano_b2b"] * (bool(r.get("veterano", False)) and b2b)
            + (c["bajas"] + c["bajas_titular"] * t) * bajas / 10
            + c["faltas"] * (r.get("faltas36", 3.0) - 3.0)
            + c["encoge"] * (b - 25.0)
        )
        out[a] = max(b + ajuste, 0.0)
    return out


# Alarma: proyeccion que se aleja de su promedio sin bajas que lo expliquen.
UMBRAL_REVISION = 8.0
BAJAS_QUE_EXPLICAN = 20.0  # minutos habituales del equipo que faltan hoy


def revisar(rotacion: dict[int, float], referencia: dict[int, float], minutos_perdidos: float,
            umbral: float = UMBRAL_REVISION, en_duda: set | frozenset = frozenset()) -> list[tuple[int, float, float]]:
    """(jugador, proyectado, promedio) de quien se aleja `umbral` minutos o mas.

    Con bajas importantes en el equipo, que los demas jueguen mas es lo
    esperado, asi que solo se revisan las caidas. El que esta en duda baja por
    su probabilidad de jugar, asi que tampoco cuenta. Sirve para atrapar
    errores como el del arranque de temporada antes de que lleguen a los props.
    """
    out = []
    for a, m in rotacion.items():
        if a in en_duda:
            continue
        ref = referencia.get(a)
        if ref is None or ref != ref:
            continue
        d = m - ref
        if abs(d) >= umbral and (minutos_perdidos < BAJAS_QUE_EXPLICAN or d < 0):
            out.append((a, round(m, 1), round(float(ref), 1)))
    return out


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
    if len(b) > MAX_JUGADORES:
        b[np.argsort(-b, kind="stable")[MAX_JUGADORES:]] = 0.0
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
