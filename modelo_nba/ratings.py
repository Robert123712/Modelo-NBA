"""Ratings por jugador, pace por equipo y contexto, con una sola regresion.

Cada partido aporta dos observaciones, una por ofensiva:

    100 * puntos / posesiones = mu_temporada
                                + h * localia
                                + sum_{i en ofensiva} s_i * o_i
                                - sum_{j en defensa}  s_j * d_j
                                + contexto

donde s_i = minutos_i / minutos_del_partido (los cinco en cancha suman 5). Es
un RAPM a nivel partido: los coeficientes salen de quien estuvo en cancha y
cuanto, no de sus estadisticas. Como a nivel partido los companeros estan muy
correlacionados, se regulariza hacia un prior que si sale de la caja (el
"box prior"), en dos pasadas:

  1. ridge hacia cero;
  2. se ajusta una regresion de esos coeficientes contra tasas de caja por 100
     posesiones, y se vuelve a ajustar el ridge hacia esa prediccion.

Asi un jugador con pocos minutos queda cerca de lo que dice su caja, y uno con
muchos se aleja de ella en la medida que los marcadores lo sostengan.

Todas las observaciones pesan por posesiones y por un decaimiento temporal: un
partido de hace `vida_media` dias pesa la mitad que uno de ayer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.linalg import cho_factor, cho_solve

ESTADISTICAS_PRIOR = [
    "points", "field_goals_attempted", "three_point_field_goals_attempted",
    "free_throws_attempted", "assists", "turnovers", "offensive_rebounds",
    "defensive_rebounds", "steals", "blocks", "fouls",
]
PRIOR_POSESIONES = 400.0


@dataclass
class Parametros:
    vida_media: float = 120.0  # dias
    # El ritmo cambia mas rapido que el talento (entrenador nuevo, plantilla
    # nueva), asi que tiene su propia memoria. None = la misma que los ratings.
    vida_media_pace: float | None = None
    lambda_jugador: float = 60.0
    lambda_temporada: float = 30.0
    lambda_contexto: float = 5.0
    lambda_pace: float = 40.0
    # Efecto de equipo (sistema, entrenador) ademas de sus jugadores. None lo
    # apaga. Muy penalizado: solo absorbe lo que los jugadores no explican.
    lambda_equipo: float | None = None
    peso_prior: bool = True
    # Valor de un jugador sin historial (novato en su debut). Medido sobre la
    # clase del draft 2025 y los 106 debutantes de 2025-26: al cierre del ano
    # quedaron cerca de cero, no muy por debajo. Ligeramente negativo porque
    # ese promedio ya esta filtrado por quien consiguio minutos.
    sin_historial_o: float = -0.3
    sin_historial_d: float = -0.3


@dataclass
class Ratings:
    corte: pd.Timestamp
    mu: dict[int, float]  # por temporada
    localia: float  # en puntos por 100 posesiones, por lado
    contexto: dict[str, float]
    ofensiva: dict[int, float]
    defensa: dict[int, float]
    pace_base: dict[int, float]
    pace_equipo: dict[int, float]
    equipo_o: dict[int, float] = field(default_factory=dict)
    equipo_d: dict[int, float] = field(default_factory=dict)
    prior_o: dict[int, float] = field(default_factory=dict)
    prior_d: dict[int, float] = field(default_factory=dict)
    params: Parametros = field(default_factory=Parametros)

    def mu_actual(self, temporada: int) -> float:
        if temporada in self.mu:
            return self.mu[temporada]
        return self.mu[max(self.mu)]

    def pace_actual(self, temporada: int) -> float:
        if temporada in self.pace_base:
            return self.pace_base[temporada]
        return self.pace_base[max(self.pace_base)]

    def jugador(self, athlete_id: int) -> tuple[float, float]:
        if athlete_id in self.ofensiva:
            return self.ofensiva[athlete_id], self.defensa[athlete_id]
        return self.params.sin_historial_o, self.params.sin_historial_d


def contexto_de(partidos: pd.DataFrame) -> pd.DataFrame:
    """Dias de descanso de cada equipo antes de cada partido.

    `b2b_*` = jugo el dia anterior (fecha del Este). El primer partido de cada
    equipo en la tabla queda como descansado.
    """
    filas = []
    for lado in ("home", "away"):
        filas.append(
            pd.DataFrame(
                {"game_id": partidos.game_id, "team": partidos[f"{lado}_id"],
                 "dia": pd.to_datetime(partidos.dia), "lado": lado}
            )
        )
    t = pd.concat(filas).sort_values(["team", "dia"])
    t["descanso"] = t.groupby("team").dia.diff().dt.days
    t["b2b"] = (t.descanso == 1).astype(float)
    w = t.pivot_table(index="game_id", columns="lado", values="b2b")
    return pd.DataFrame(
        {"game_id": w.index, "b2b_home": w["home"].values, "b2b_away": w["away"].values}
    )


def _pesos(partidos: pd.DataFrame, corte: pd.Timestamp, vida_media: float):
    edad = (corte - partidos.fecha).dt.total_seconds() / 86400.0
    return np.power(0.5, edad.values / vida_media)


def _observaciones(partidos: pd.DataFrame, jugadores: pd.DataFrame):
    """Matriz de en-cancha por (partido, ofensiva) y vector de ORtg."""
    pid_idx = {g: k for k, g in enumerate(partidos.game_id.values)}
    jugaron = jugadores[jugadores.minutes > 0]
    jugaron = jugaron[jugaron.game_id.isin(pid_idx)]
    ids = np.sort(jugaron.athlete_id.unique())
    col = {a: k for k, a in enumerate(ids)}
    n = len(partidos)

    home_of = dict(zip(partidos.game_id, partidos.home_id))
    minutos = dict(zip(partidos.game_id, partidos.minutos_juego))
    g = jugaron.game_id.map(pid_idx).values
    es_local = (jugaron.team_id.values == jugaron.game_id.map(home_of).values)
    s = jugaron.minutes.values / jugaron.game_id.map(minutos).values
    c = jugaron.athlete_id.map(col).values
    # Fila k = ofensiva local del partido k; fila n + k = ofensiva visitante.
    fila_of = np.where(es_local, g, n + g)
    fila_def = np.where(es_local, n + g, g)
    P = len(ids)
    rows = np.concatenate([fila_of, fila_def])
    cols = np.concatenate([c, P + c])
    vals = np.concatenate([s, -s])
    X = sp.csr_matrix((vals, (rows, cols)), shape=(2 * n, 2 * P))

    y = np.concatenate([
        100 * partidos.home_pts.values / partidos.posesiones.values,
        100 * partidos.away_pts.values / partidos.posesiones.values,
    ])
    return X, y, ids


def _prior_de_caja(partidos, jugadores, ids, peso_partido, o, d):
    """Regresion de los coeficientes contra tasas de caja por 100 posesiones."""
    pos = dict(zip(partidos.game_id, partidos.posesiones))
    minutos = dict(zip(partidos.game_id, partidos.minutos_juego))
    w_partido = dict(zip(partidos.game_id, peso_partido))
    j = jugadores[(jugadores.minutes > 0) & jugadores.game_id.isin(pos)].copy()
    frac = j.minutes / j.game_id.map(minutos)
    j["pos_j"] = j.game_id.map(pos) * frac
    j["w"] = j.game_id.map(w_partido)
    agg = {}
    for st in ESTADISTICAS_PRIOR + ["pos_j", "minutes"]:
        agg[st] = (j[st] * j.w).groupby(j.athlete_id).sum()
    juegos = j.groupby("athlete_id").w.sum()
    A = pd.DataFrame(agg).reindex(ids).fillna(0.0)
    pos_j = A.pop("pos_j")
    mins = A.pop("minutes")
    # Tasas encogidas hacia la de la liga: con 40 posesiones, un jugador que
    # anoto 12 "anota 30 por 100", y la regresion extrapola ese ruido a un prior
    # de estrella. Con PRIOR_POSESIONES de muestra ficticia, pesa poco el ruido.
    liga = A.sum() / pos_j.sum()
    tasas = (A + PRIOR_POSESIONES * liga).div(pos_j + PRIOR_POSESIONES, axis=0) * 100
    mpg = (mins / juegos.reindex(ids).clip(lower=1e-6)).values
    # El ajuste solo ve jugadores con muestra (mpg de ~5 a ~38). Fuera de ese
    # rango la raiz extrapola: un jugador de un minuto salia con prior de
    # estrella. Se acota al rango observado.
    mpg = np.clip(mpg, 6.0, 38.0)
    F = np.column_stack([np.ones(len(ids)), tasas.values, mpg, np.sqrt(mpg)])
    # Se ajusta solo con quien tiene muestra; el resto recibe la prediccion.
    peso = np.minimum(mins.values, 1500.0)
    ok = mins.values >= 150
    W = peso[ok]
    def ajusta(objetivo):
        Fw = F[ok] * W[:, None]
        beta = np.linalg.solve(Fw.T @ F[ok] + 1e-3 * np.eye(F.shape[1]), Fw.T @ objetivo[ok])
        return F @ beta
    return ajusta(o), ajusta(d)


def ajustar(
    partidos: pd.DataFrame,
    jugadores: pd.DataFrame,
    corte: pd.Timestamp,
    params: Parametros | None = None,
) -> Ratings:
    """Ratings con todo lo jugado antes de `corte`."""
    params = params or Parametros()
    partidos = partidos[partidos.fecha < corte].reset_index(drop=True)
    if partidos.empty:
        raise ValueError("No hay partidos antes del corte")
    jugadores = jugadores[jugadores.game_id.isin(partidos.game_id)]
    n = len(partidos)

    peso_partido = _pesos(partidos, corte, params.vida_media) * partidos.posesiones.values / 100
    w = np.concatenate([peso_partido, peso_partido])

    Xj, y, ids = _observaciones(partidos, jugadores)
    P = len(ids)

    # Columnas fijas: temporadas, localia y contexto.
    temporadas = np.sort(partidos.season.unique())
    t_idx = {t: k for k, t in enumerate(temporadas)}
    tcol = partidos.season.map(t_idx).values
    T = len(temporadas)
    Xt = sp.csr_matrix(
        (np.ones(2 * n), (np.arange(2 * n), np.concatenate([tcol, tcol]))), shape=(2 * n, T)
    )
    neutral = partidos.neutral.values
    loc = np.where(neutral, 0.0, 1.0)
    localia = np.concatenate([loc, -loc])
    ctx = contexto_de(partidos).set_index("game_id").reindex(partidos.game_id).fillna(0.0)
    b2b_h, b2b_a = ctx.b2b_home.values, ctx.b2b_away.values
    # b2b de la ofensiva y b2b de la defensa, como columnas separadas.
    b2b_of = np.concatenate([b2b_h, b2b_a])
    b2b_def = np.concatenate([b2b_a, b2b_h])
    Xc = sp.csr_matrix(np.column_stack([localia, b2b_of, b2b_def]))
    equipos = np.sort(np.unique(np.r_[partidos.home_id.values, partidos.away_id.values]))
    E = len(equipos) if params.lambda_equipo is not None else 0
    bloques = [Xt, Xc]
    if E:
        e_idx = {e: k for k, e in enumerate(equipos)}
        of = np.concatenate([partidos.home_id.map(e_idx).values, partidos.away_id.map(e_idx).values])
        de = np.concatenate([partidos.away_id.map(e_idx).values, partidos.home_id.map(e_idx).values])
        filas = np.arange(2 * n)
        bloques.append(sp.csr_matrix(
            (np.r_[np.ones(2 * n), -np.ones(2 * n)], (np.r_[filas, filas], np.r_[of, E + de])),
            shape=(2 * n, 2 * E),
        ))
    X = sp.hstack(bloques + [Xj]).tocsr()
    J0 = T + 3 + 2 * E  # primera columna de jugadores
    nombres_ctx = ["localia", "b2b_ofensiva", "b2b_defensa"]

    pen = np.concatenate([
        np.r_[0.0, np.full(T - 1, params.lambda_temporada)],
        np.full(3, params.lambda_contexto),
        np.full(2 * E, params.lambda_equipo or 0.0),
        np.full(2 * P, params.lambda_jugador),
    ])
    # Las temporadas posteriores a la primera se codifican como desviacion de
    # la anterior: penalizarlas tira de mu hacia la temporada previa cuando la
    # actual tiene pocos partidos, en vez de hacia cero.
    D = np.eye(T)
    for k in range(1, T):
        D[k, k - 1] = -1.0

    def resolver(prior_vec):
        Xw = X.multiply(w[:, None]).tocsr()
        XtX = (Xw.T @ X).toarray()
        Xty = Xw.T @ (y - X @ prior_vec)
        R = np.diag(pen)
        R[:T, :T] = D.T @ np.diag(pen[:T]) @ D
        delta = cho_solve(cho_factor(XtX + R + 1e-6 * np.eye(X.shape[1])), Xty)
        return prior_vec + delta

    prior = np.zeros(X.shape[1])
    beta = resolver(prior)
    o, d = beta[J0 : J0 + P], beta[J0 + P :]
    prior_o = prior_d = np.zeros(P)
    if params.peso_prior:
        prior_o, prior_d = _prior_de_caja(partidos, jugadores, ids, peso_partido, o, d)
        prior[J0 : J0 + P] = prior_o
        prior[J0 + P :] = prior_d
        beta = resolver(prior)
        o, d = beta[J0 : J0 + P], beta[J0 + P :]

    mu = {int(t): float(v) for t, v in zip(temporadas, beta[:T])}
    contexto = {k: float(v) for k, v in zip(nombres_ctx, beta[T : T + 3])}

    peso_pace = peso_partido
    if params.vida_media_pace is not None:
        peso_pace = _pesos(partidos, corte, params.vida_media_pace) * partidos.posesiones.values / 100
    pace_base, pace_equipo = _ajustar_pace(partidos, peso_pace, params)
    return Ratings(
        corte=corte,
        mu=mu,
        localia=contexto.pop("localia"),
        contexto=contexto,
        ofensiva=dict(zip(ids.tolist(), o.tolist())),
        defensa=dict(zip(ids.tolist(), d.tolist())),
        pace_base=pace_base,
        pace_equipo=pace_equipo,
        equipo_o=dict(zip(equipos.tolist(), beta[T + 3 : T + 3 + E].tolist())) if E else {},
        equipo_d=dict(zip(equipos.tolist(), beta[T + 3 + E : T + 3 + 2 * E].tolist())) if E else {},
        prior_o=dict(zip(ids.tolist(), np.asarray(prior_o).tolist())),
        prior_d=dict(zip(ids.tolist(), np.asarray(prior_d).tolist())),
        params=params,
    )


def _ajustar_pace(partidos, peso, params):
    """Posesiones por 48 = base de la temporada + efecto local + efecto visita."""
    y = 48 * partidos.posesiones.values / partidos.minutos_juego.values
    equipos = np.sort(np.unique(np.r_[partidos.home_id.values, partidos.away_id.values]))
    e_idx = {e: k for k, e in enumerate(equipos)}
    temporadas = np.sort(partidos.season.unique())
    t_idx = {t: k for k, t in enumerate(temporadas)}
    n, E, T = len(partidos), len(equipos), len(temporadas)
    X = np.zeros((n, T + E))
    X[np.arange(n), partidos.season.map(t_idx).values] = 1.0
    X[np.arange(n), T + partidos.home_id.map(e_idx).values] += 1.0
    X[np.arange(n), T + partidos.away_id.map(e_idx).values] += 1.0
    pen = np.r_[np.zeros(T), np.full(E, params.lambda_pace)]
    Xw = X * peso[:, None]
    beta = np.linalg.solve(Xw.T @ X + np.diag(pen) + 1e-6 * np.eye(T + E), Xw.T @ y)
    return (
        {int(t): float(v) for t, v in zip(temporadas, beta[:T])},
        {int(e): float(v) for e, v in zip(equipos, beta[T:])},
    )
