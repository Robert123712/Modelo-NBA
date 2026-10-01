"""Backtest walk-forward: cada dia se ajusta con lo jugado antes y se proyecta.

La disponibilidad se toma del box score: un jugador cuenta si no fue baja por
lesion o ausencia. Eso equivale a conocer la lista de inactivos, que es lo que
la corrida oficial (60 minutos antes) tiene casi siempre. No ve quien recibio
minutos ni cuantos: los minutos salen de la base previa al partido.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import minutos as mn
from .proyeccion import esperar
from .ratings import Parametros, Ratings, ajustar, contexto_de

ET = "America/New_York"


def rotaciones(jm: pd.DataFrame, game_id: int) -> dict[int, dict[int, float]]:
    """Base de minutos de los disponibles de cada equipo en un partido."""
    g = jm[(jm.game_id == game_id) & jm.disponible]
    return {
        int(t): dict(zip(x.athlete_id.astype(int), x.m_base))
        for t, x in g.groupby("team_id")
    }


def correr(
    partidos: pd.DataFrame,
    jugadores: pd.DataFrame,
    temporada: int,
    params: Parametros | None = None,
    cada_dias: int = 1,
    tipos=(2, 3, 5),
) -> pd.DataFrame:
    params = params or Parametros()
    jm = mn.con_minutos_previos(jugadores, partidos)
    por_partido = {gid: x for gid, x in jm[jm.disponible].groupby("game_id")}
    ctx = contexto_de(partidos).set_index("game_id")
    objetivo = partidos[(partidos.season == temporada) & partidos.season_type.isin(tipos)]

    filas = []
    R: Ratings | None = None
    ultimo_ajuste = None
    for dia, juegos in objetivo.groupby("dia"):
        corte = pd.Timestamp(dia).tz_localize(ET).tz_convert("UTC")
        if R is None or (corte - ultimo_ajuste).days >= cada_dias:
            R = ajustar(partidos, jugadores, corte, params)
            ultimo_ajuste = corte
        for _, p in juegos.iterrows():
            disp = por_partido.get(p.game_id)
            if disp is None:
                continue
            rot = {
                int(t): mn.repartir(dict(zip(x.athlete_id.astype(int), x.m_base)))
                for t, x in disp.groupby("team_id")
            }
            if p.home_id not in rot or p.away_id not in rot:
                continue
            c = ctx.loc[p.game_id] if p.game_id in ctx.index else None
            e = esperar(
                R, int(p.season), int(p.home_id), int(p.away_id),
                rot[p.home_id], rot[p.away_id], bool(p.neutral),
                bool(c is not None and c.b2b_home == 1),
                bool(c is not None and c.b2b_away == 1),
            )
            filas.append({
                "game_id": p.game_id, "dia": dia, "season_type": p.season_type,
                "pred_casa": e.puntos_casa, "pred_visita": e.puntos_visita,
                "pred_pace": e.pace,
                "real_casa": p.home_pts, "real_visita": p.away_pts,
                "real_1h_casa": p.home_1h, "real_1h_visita": p.away_1h,
                "real_reg_casa": p.home_reg, "real_reg_visita": p.away_reg,
                "periodos": p.periodos, "posesiones": p.posesiones,
                "minutos_juego": p.minutos_juego,
            })
    return pd.DataFrame(filas)


def resumen(bt: pd.DataFrame, cierre: pd.DataFrame | None = None) -> dict:
    """Errores del modelo y, si hay cierre, del mercado sobre los mismos juegos."""
    b = bt.copy()
    # La proyeccion es de reglamento; el real incluye OT. Para comparar con el
    # mercado (que tambien cotiza el partido completo) se compara completo.
    b["pred_margen"] = b.pred_casa - b.pred_visita
    b["pred_total"] = b.pred_casa + b.pred_visita
    b["margen"] = b.real_casa - b.real_visita
    b["total"] = b.real_casa + b.real_visita
    out = {
        "n": len(b),
        "mae_margen": float(np.mean(np.abs(b.margen - b.pred_margen))),
        "mae_total": float(np.mean(np.abs(b.total - b.pred_total))),
        "sesgo_total": float(np.mean(b.total - b.pred_total)),
        "sesgo_margen": float(np.mean(b.margen - b.pred_margen)),
    }
    if cierre is not None:
        m = b.merge(cierre, on="game_id")
        out["n_cierre"] = len(m)
        out["mae_margen_modelo"] = float(np.mean(np.abs(m.margen - m.pred_margen)))
        out["mae_margen_cierre"] = float(np.mean(np.abs(m.margen + m.linea_casa)))
        out["mae_total_modelo"] = float(np.mean(np.abs(m.total - m.pred_total)))
        out["mae_total_cierre"] = float(np.mean(np.abs(m.total - m.total_cierre)))
        out["corr_margen_vs_cierre"] = float(np.corrcoef(m.pred_margen, -m.linea_casa)[0, 1])
        out["corr_total_vs_cierre"] = float(np.corrcoef(m.pred_total, m.total_cierre)[0, 1])
    return out


def residuos_por_mitad(bt: pd.DataFrame, parte_1h: float) -> np.ndarray:
    """Residuos (1a casa, 2a casa, 1a visita, 2a visita) en reglamento.

    Es la covarianza que usa el simulador. Sale de prediccion walk-forward, asi
    que mide el error predictivo completo: el del modelo mas el azar.
    """
    b = bt.dropna(subset=["real_1h_casa", "real_reg_casa"])
    return np.column_stack([
        b.real_1h_casa - parte_1h * b.pred_casa,
        b.real_reg_casa - b.real_1h_casa - (1 - parte_1h) * b.pred_casa,
        b.real_1h_visita - parte_1h * b.pred_visita,
        b.real_reg_visita - b.real_1h_visita - (1 - parte_1h) * b.pred_visita,
    ])


def evaluar(bt: pd.DataFrame, cierre: pd.DataFrame, ps) -> tuple[dict, pd.DataFrame]:
    """Simula cada partido del backtest y lo califica como se calificara en vivo.

    A diferencia de `resumen`, usa la distribucion completa (con OT), asi que
    compara lo mismo que se publica: mediana de margen, media de total y
    probabilidades.
    """
    from .mercados import mercados
    from .simulador import simular

    filas = []
    for r in bt.itertuples():
        m = mercados(simular(r.pred_casa, r.pred_visita, ps, semilla=int(r.game_id)))
        filas.append({
            "game_id": r.game_id,
            "p_casa": m["ganador"]["casa"],
            "margen_modelo": m["margen"]["media"],
            "total_modelo": m["total"]["media"],
            "m10": m["margen"]["p10"], "m90": m["margen"]["p90"],
            "t10": m["total"]["p10"], "t90": m["total"]["p90"],
            "p1h_casa": m["primera_mitad"]["casa"],
            "total_1h_modelo": m["primera_mitad"]["total"]["media"],
            "ot_modelo": m["tiempo_extra"],
        })
    e = bt.merge(pd.DataFrame(filas), on="game_id").merge(cierre, on="game_id", how="left")
    e["margen"] = e.real_casa - e.real_visita
    e["total"] = e.real_casa + e.real_visita
    e["gana_casa"] = (e.margen > 0).astype(float)
    con = e.dropna(subset=["linea_casa"])

    def brier(p, y):
        return float(np.mean((p - y) ** 2))

    def logloss(p, y):
        p = np.clip(p, 1e-4, 1 - 1e-4)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    from math import erf, sqrt

    # Probabilidad del cierre, de su spread con la desviacion historica del
    # margen alrededor de la linea (13.5). Es la referencia justa para el Brier.
    p_cierre = con.linea_casa.map(lambda l: 0.5 * (1 + erf((-l) / (13.5 * sqrt(2)))))

    # Contra la linea: lado que el modelo prefiere respecto al spread de cierre.
    dif = con.margen_modelo + con.linea_casa  # >0: el modelo ve a la casa mejor que la linea
    cubre = con.margen + con.linea_casa
    jugadas = (cubre != 0)
    acierto_ats = ((np.sign(dif) == np.sign(cubre)) & jugadas)
    difer_t = con.total_modelo - con.total_cierre
    real_t = con.total - con.total_cierre
    acierto_ou = (np.sign(difer_t) == np.sign(real_t)) & (real_t != 0)

    def ats(umbral):
        sel = (dif.abs() >= umbral) & jugadas
        return {"n": int(sel.sum()), "acierto": round(float(acierto_ats[sel].mean()), 4) if sel.any() else None}

    def ou(umbral):
        sel = (difer_t.abs() >= umbral) & (real_t != 0)
        return {"n": int(sel.sum()), "acierto": round(float(acierto_ou[sel].mean()), 4) if sel.any() else None}

    real1h = e.real_1h_casa + e.real_1h_visita
    out = {
        "n": len(e),
        "n_con_cierre": len(con),
        "margen": {
            "mae_modelo": round(float(np.mean(np.abs(con.margen - con.margen_modelo))), 3),
            "mae_cierre": round(float(np.mean(np.abs(con.margen + con.linea_casa))), 3),
            "sesgo_modelo": round(float(np.mean(con.margen - con.margen_modelo)), 3),
            "cobertura_80": round(float(((e.margen >= e.m10) & (e.margen <= e.m90)).mean()), 3),
        },
        "total": {
            "mae_modelo": round(float(np.mean(np.abs(con.total - con.total_modelo))), 3),
            "mae_cierre": round(float(np.mean(np.abs(con.total - con.total_cierre))), 3),
            "sesgo_modelo": round(float(np.mean(con.total - con.total_modelo)), 3),
            "cobertura_80": round(float(((e.total >= e.t10) & (e.total <= e.t90)).mean()), 3),
        },
        "ganador": {
            "brier_modelo": round(brier(con.p_casa, con.gana_casa), 4),
            "brier_cierre": round(brier(p_cierre, con.gana_casa), 4),
            "logloss_modelo": round(logloss(con.p_casa, con.gana_casa), 4),
            "logloss_cierre": round(logloss(p_cierre, con.gana_casa), 4),
            "acierto_modelo": round(float(((con.p_casa > 0.5) == (con.gana_casa == 1)).mean()), 4),
        },
        "contra_cierre_spread": {f">={u}": ats(u) for u in (0, 2, 4, 6)},
        "contra_cierre_total": {f">={u}": ou(u) for u in (0, 3, 6, 9)},
        "primera_mitad": {
            "mae_total": round(float(np.nanmean(np.abs(real1h - e.total_1h_modelo))), 3),
            "brier_ganador": round(brier(e.p1h_casa[e.real_1h_casa != e.real_1h_visita],
                                         (e.real_1h_casa > e.real_1h_visita)[e.real_1h_casa != e.real_1h_visita].astype(float)), 4),
        },
        "tiempo_extra": {
            "modelo": round(float(e.ot_modelo.mean()), 4),
            "real": round(float((e.periodos > 4).mean()), 4),
        },
    }
    return out, e
