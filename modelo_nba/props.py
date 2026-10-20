"""Props de jugador: puntos, rebotes, asistencias y sus combinados.

Un prop es minutos por produccion. Los minutos ya los proyecta `minutos.py`
con las bajas del dia; aqui se agrega lo que cada jugador produce, y se simula
junto con el partido para que las dos cosas se muevan juntas:

* **Tasa por posesion en cancha**, con memoria reciente y encogida hacia la
  liga. Por posesion y no por minuto, para que el ritmo del partido entre solo.
* **Puntos amarrados al marcador del equipo.** Cada jugador se lleva su parte
  de los puntos que el simulador le da a su equipo en esa simulacion: si el
  equipo anota 130, sus jugadores anotan mas; los puntos de la rotacion no
  pueden contradecir al marcador.
* **Rebotes y asistencias ajustados por rival**: lo que cada defensa permite
  por posesion, respecto a la liga.
* **Paliza.** Por cada punto de margen arriba de 8, los titulares pierden
  minutos (medido: 32 en partido cerrado, 26 con 30+ de diferencia). Por eso
  el prop sale de simular el partido, no de un promedio.
* **Ruido.** Los puntos varian ~2.5 veces lo que daria un conteo simple
  (Poisson); rebotes y asistencias casi nada. Cada estadistica tiene su
  dispersion, y las tres de un jugador comparten sus minutos simulados, asi
  que los combinados (PRA, P+R, P+A) salen correlacionados, no sumados.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .minutos import no_disponible

STATS = ("points", "reb", "assists")
COMBOS = {"pra": ("points", "reb", "assists"), "pr": ("points", "reb"), "pa": ("points", "assists")}
ROTACION = 8


@dataclass
class ParametrosProps:
    vida_media_partidos: float = 60.0
    # Posesiones ficticias con la tasa de la liga: cuanto se encoge un jugador
    # con poca muestra.
    prior_posesiones: dict[str, float] = field(
        default_factory=lambda: {"points": 300.0, "reb": 300.0, "assists": 300.0}
    )
    # Exponente del ajuste por rival (0 = no se ajusta, 1 = completo).
    peso_rival: dict[str, float] = field(default_factory=lambda: {"reb": 1.0, "assists": 1.0})
    # Varianza / media de cada estadistica con los minutos ya fijos.
    dispersion: dict[str, float] = field(
        default_factory=lambda: {"points": 2.4, "reb": 1.05, "assists": 1.05}
    )
    sd_minutos: float = 6.0
    paliza_umbral: float = 8.0
    paliza_pendiente: float = 0.27  # minutos por punto de margen, titulares
    # Mezcla final de la media: (simulacion, promedio de la temporada, ultimos
    # 10). Ajustada por minimos cuadrados en 2024-25; los promedios traen el
    # rol reciente que la tasa de largo plazo no ve.
    mezcla: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: {
            "points": (0.668, 0.209, 0.166),
            "reb": (0.573, 0.236, 0.213),
            "assists": (0.623, 0.171, 0.226),
        }
    )
    # Defensa contra un grupo de jugadores: None (solo el equipo), "posicion"
    # (G/F/C de ESPN) o "rol" (sacado de sus estadisticas).
    # Probado en 2024-25 y a ciegas en 2025-26 (docs/PROPS.md): solo en
    # asistencias y por posicion la defensa por grupo mejora; en puntos y
    # rebotes es ruido, y ahi se queda la de equipo.
    grupo: str | None = "posicion"
    vida_dvp_dias: float = 180.0
    # Unidades ficticias de "lo esperado" que encogen el factor hacia 1.
    prior_dvp: dict[str, float] = field(
        default_factory=lambda: {"points": 150.0, "reb": 60.0, "assists": 40.0}
    )
    peso_dvp: dict[str, float] = field(
        default_factory=lambda: {"points": 0.0, "reb": 0.0, "assists": 1.0}
    )
    # Companeros fuera: que fraccion de lo que producian los ausentes se queda
    # en el equipo (0 = se pierde, 1 = el total del equipo se conserva). Solo
    # asistencias mejoro; en rebotes no.
    beta_bajas: dict[str, float] = field(default_factory=lambda: {"reb": 0.0, "assists": 0.5})


def tabla_jugador_partido(jugadores: pd.DataFrame, partidos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por jugador que jugo, con sus posesiones en cancha."""
    info = partidos.set_index("game_id")[["fecha", "season", "season_type", "posesiones", "minutos_juego", "home_id", "away_id"]]
    j = jugadores[jugadores.minutes > 0].join(info, on="game_id", how="inner").copy()
    j["reb"] = j.offensive_rebounds + j.defensive_rebounds
    j["pos"] = j.posesiones * j.minutes / j.minutos_juego
    j["rival"] = np.where(j.team_id == j.home_id, j.away_id, j.home_id)
    return j.sort_values(["athlete_id", "fecha"]).reset_index(drop=True)


@dataclass
class Tasas:
    jugador: pd.DataFrame  # index athlete_id, columnas = STATS (por 100 posesiones)
    rival: pd.DataFrame  # index team_id, factor permitido / liga por estadistica
    liga: dict[str, float]
    # Con `grupo`: el grupo de cada jugador y, por (defensa, grupo), cuanto
    # permite contra lo que esos mismos jugadores suelen producir.
    grupo: pd.Series | None = None
    dvp: pd.DataFrame | None = None


ROLES = {
    "creador": "bases",
    "pivot": "pívots",
    "abierto": "ala-pívots",
    "tirador": "tiradores",
    "alero": "aleros",
}
POSICIONES = {"G": "guardias", "F": "aleros", "C": "centros"}


def posiciones(tabla: pd.DataFrame) -> pd.Series:
    """La ultima posicion conocida de cada jugador (G, F o C)."""
    if "posicion" not in tabla:
        return pd.Series(dtype=object)
    t = tabla.dropna(subset=["posicion"])
    return t.groupby("athlete_id").posicion.last()


def roles(tabla: pd.DataFrame, antes_de) -> pd.Series:
    """Rol de cada jugador por como juega, no por su etiqueta.

    Con su ultimo ano (minimo 300 posesiones): el que mas asiste es
    "creador"; el que mas rebotea es "pivot" si casi no tira de tres y
    "abierto" si si; el que mas tira de tres es "tirador"; el resto, "alero".
    Los cortes son cuantiles de la liga, asi que no dependen de la epoca.
    """
    t = tabla[(tabla.fecha < antes_de) & (tabla.fecha >= antes_de - pd.Timedelta(days=365))]
    g = t.groupby("athlete_id")[["pos", "reb", "assists", "three_point_field_goals_attempted"]].sum()
    g = g[g.pos >= 300]
    r = g[["reb", "assists", "three_point_field_goals_attempted"]].div(g.pos, axis=0)
    ast_q, reb_q = r.assists.quantile(0.75), r.reb.quantile(0.75)
    tres_med, tres_alto = r.three_point_field_goals_attempted.quantile([0.5, 0.67])
    rol = pd.Series("alero", index=r.index, dtype=object)
    rol[r.three_point_field_goals_attempted >= tres_alto] = "tirador"
    grande = r.reb >= reb_q
    rol[grande & (r.three_point_field_goals_attempted < tres_med)] = "pivot"
    rol[grande & (r.three_point_field_goals_attempted >= tres_med)] = "abierto"
    rol[(r.assists >= ast_q) & ~grande] = "creador"
    return rol


def defensa_por_grupo(t: pd.DataFrame, jug: pd.DataFrame, liga: dict, grupo: pd.Series,
                      antes_de, params: ParametrosProps) -> pd.DataFrame:
    """Cuanto produce cada grupo contra cada defensa, contra lo esperado.

    Lo esperado de cada jugador es su propia tasa por sus posesiones de ese
    partido, asi que enfrentar a un grupo de buenos reboteadores no infla a la
    defensa: solo cuenta lo que se hizo de mas o de menos. Encogido hacia 1 con
    `prior_dvp` y normalizado para que el promedio de cada grupo sea 1.
    """
    t = t[t.fecha >= antes_de - pd.Timedelta(days=365)].copy()
    t["grupo"] = t.athlete_id.map(grupo)
    t = t.dropna(subset=["grupo"])
    dias = (antes_de - t.fecha).dt.total_seconds() / 86400
    w = np.power(0.5, dias / params.vida_dvp_dias)
    cols = {}
    for s in STATS:
        tasa = t.athlete_id.map(jug[s]).fillna(liga[s])
        cols[f"A_{s}"] = t[s] * w
        cols[f"E_{s}"] = tasa * t.pos / 100 * w
    x = pd.DataFrame(cols).assign(rival=t.rival.values, grupo=t.grupo.values)
    agg = x.groupby(["rival", "grupo"]).sum()
    tot = x.groupby("grupo").sum()
    out = {}
    for s in STATS:
        k = params.prior_dvp[s]
        base = (tot[f"A_{s}"] / tot[f"E_{s}"]).reindex(agg.index.get_level_values("grupo")).values
        out[s] = (agg[f"A_{s}"] + k * base) / (agg[f"E_{s}"] + k) / base
    return pd.DataFrame(out)


def tasas(tabla: pd.DataFrame, antes_de, params: ParametrosProps | None = None) -> Tasas:
    """Tasas por 100 posesiones de cada jugador y lo que permite cada defensa."""
    params = params or ParametrosProps()
    t = tabla[tabla.fecha < antes_de]
    liga = {s: float(t[s].sum() / t.pos.sum() * 100) for s in STATS}

    # Peso por recencia en partidos del propio jugador.
    orden = t.groupby("athlete_id").cumcount(ascending=False)
    w = np.power(0.5, orden.values / params.vida_media_partidos)
    pos_w = (t.pos * w).groupby(t.athlete_id).sum()
    filas = {}
    for s in STATS:
        k = params.prior_posesiones[s]
        suma = (t[s] * w).groupby(t.athlete_id).sum()
        filas[s] = (suma + k * liga[s] / 100) / (pos_w + k) * 100
    jug = pd.DataFrame(filas)

    # Lo que permite cada defensa: lo que sus rivales produjeron contra ella en
    # sus ultimos ~25 partidos, por posesion, contra la liga.
    por_partido = t.groupby(["game_id", "rival"])[list(STATS) + ["pos"]].sum().reset_index()
    por_partido = por_partido.merge(t[["game_id", "fecha"]].drop_duplicates("game_id"), on="game_id")
    por_partido = por_partido.sort_values("fecha").groupby("rival").tail(25)
    agg = por_partido.groupby("rival")[list(STATS) + ["pos"]].sum()
    rival = pd.DataFrame({s: (agg[s] / agg.pos * 100) / liga[s] for s in STATS})
    if params.grupo is None:
        return Tasas(jug, rival, liga)
    grupo = posiciones(t) if params.grupo == "posicion" else roles(t, antes_de)
    if grupo.empty:
        return Tasas(jug, rival, liga)
    return Tasas(jug, rival, liga, grupo, defensa_por_grupo(t, jug, liga, grupo, antes_de, params))


def promedios(tabla: pd.DataFrame, antes_de, temporada: int) -> pd.DataFrame:
    """Promedio por partido de la temporada y de los ultimos 10, por jugador.

    Con menos de 3 partidos en la temporada, el de la temporada usa sus ultimos
    30 (temporada pasada). Sin historial no hay fila y la mezcla no aplica.
    """
    t = tabla[(tabla.fecha < antes_de) & (tabla.season_type != 3)]
    g = t.groupby("athlete_id")
    ult10 = g[list(STATS)].apply(lambda x: x.tail(10).mean())
    ult30 = g[list(STATS)].apply(lambda x: x.tail(30).mean())
    tt = t[t.season == temporada].groupby("athlete_id")
    temp = tt[list(STATS)].mean()
    temp = temp[tt.size() >= 3].reindex(ult30.index).fillna(ult30)
    return pd.concat({"temporada": temp, "ult10": ult10}, axis=1)


def _rotacion(minutos: dict[int, float], n: int = ROTACION) -> list[int]:
    return [a for a, m in sorted(minutos.items(), key=lambda x: -x[1])[:n] if m >= 8]


def simular_props(
    T: Tasas,
    minutos: dict[str, dict[int, float]],  # lado -> {athlete_id: minutos proyectados}
    equipos: dict[str, int],  # lado -> team_id
    puntos_equipo: dict[str, np.ndarray],  # lado -> puntos simulados del equipo (final)
    margen_casa: np.ndarray,
    pace: float,
    params: ParametrosProps | None = None,
    semilla: int | None = None,
    jugadores: list[int] | None = None,
    prom: pd.DataFrame | None = None,
    minutos_completos: dict[str, dict[int, float]] | None = None,
) -> dict[int, dict]:
    """Simulaciones por jugador de cada estadistica.

    `jugadores` limita a quien se simula (por omision, la rotacion de 8 de cada
    lado); el reparto de puntos usa siempre a todo el equipo. `prom` (de
    `promedios`) activa la mezcla con los promedios recientes.
    `minutos_completos` (los minutos con el roster sano) activa el efecto de
    companeros fuera. Cada jugador trae ademas `info`: lo que movio su
    proyeccion, para explicarla.
    """
    params = params or ParametrosProps()
    rng = np.random.default_rng(semilla)
    n = len(margen_casa)
    out: dict[int, dict[str, np.ndarray]] = {}
    for lado, rival_lado in (("home", "away"), ("away", "home")):
        mins = minutos[lado]
        ids = [a for a, m in mins.items() if m > 0]
        if not ids:
            continue
        m = np.array([mins[a] for a in ids])
        titulares = np.zeros(len(ids), bool)
        titulares[np.argsort(-m)[:5]] = True

        # Minutos simulados: ruido propio + lo que quita una paliza a los
        # titulares, repartido entre la banca.
        exceso = np.maximum(np.abs(margen_casa) - params.paliza_umbral, 0.0)
        quita = params.paliza_pendiente * exceso
        ms = m[None, :] + rng.normal(0, params.sd_minutos, (n, len(ids)))
        ms[:, titulares] -= quita[:, None]
        banca = ~titulares
        if banca.any():
            peso_b = m[banca] / m[banca].sum()
            ms[:, banca] += (quita * titulares.sum())[:, None] * peso_b[None, :]
        ms = np.clip(ms, 0, 48)
        frac = np.where(m[None, :] > 0, ms / m[None, :], 0.0)

        tasa = T.jugador.reindex(ids)
        for s in STATS:
            tasa[s] = tasa[s].fillna(T.liga[s])
        pos_jug = pace * m / 48  # posesiones en cancha esperadas

        # Puntos: parte del marcador del equipo en cada simulacion.
        base_pts = tasa["points"].values * pos_jug / 100
        cuota = base_pts / base_pts.sum()
        media = {"points": cuota[None, :] * puntos_equipo[lado][:, None] * frac}
        rival = equipos[rival_lado]
        con_grupo = T.dvp is not None and T.grupo is not None
        # Estadisticas que usan defensa por grupo; las demas se quedan con la
        # de equipo.
        por_grupo = {s for s in STATS if con_grupo and params.peso_dvp.get(s, 0.0) > 0}
        for s in ("reb", "assists"):
            # Sin grupos, el ajuste por equipo va antes de la mezcla (como se
            # afino la v1); con grupos, el de grupo va despues.
            f = 1.0
            if s not in por_grupo and s in T.rival:
                f = T.rival[s].get(rival, 1.0) ** params.peso_rival.get(s, 0.0)
            media[s] = (tasa[s].values * pos_jug / 100 * f)[None, :] * frac

        # Contexto que se aplica despues de la mezcla, porque los promedios
        # recientes no lo saben: defensa contra su grupo y companeros fuera.
        ctx = {s: np.ones(len(ids)) for s in STATS}
        grupos = [None] * len(ids)
        if con_grupo:
            grupos = [T.grupo.get(a) for a in ids]
            for s in por_grupo:
                f = np.array([
                    T.dvp[s].get((rival, g), 1.0) if g is not None else 1.0 for g in grupos
                ]) ** params.peso_dvp.get(s, 0.0)
                if s == "points":
                    # Cambia el reparto, no el marcador: el que tiene buen
                    # duelo se lleva mas de los mismos puntos.
                    f = f / float((cuota * f).sum())
                ctx[s] = ctx[s] * f
        rival_ctx = {s: ctx[s].copy() for s in STATS}
        # Para explicar: el ajuste por equipo va antes de la mezcla, asi que
        # pesa lo que pesa la simulacion en ella.
        for s in ("reb", "assists"):
            if s not in por_grupo and s in T.rival:
                f = T.rival[s].get(rival, 1.0) ** params.peso_rival.get(s, 0.0)
                rival_ctx[s][:] = 1 + (f - 1) * (params.mezcla[s][0] if prom is not None else 1.0)
        bajas_ctx = {s: np.ones(len(ids)) for s in STATS}
        completos = (minutos_completos or {}).get(lado)
        m_full = np.array([completos.get(a, 0.0) for a in ids]) if completos else None
        if completos:
            full_ids = [a for a, mm in completos.items() if mm > 0]
            tf = T.jugador.reindex(full_ids)
            mf = np.array([completos[a] for a in full_ids])
            for s in ("reb", "assists"):
                e_full = float((tf[s].fillna(T.liga[s]).values * mf).sum())
                e_disp = float((tasa[s].values * m).sum())
                if e_disp > 0:
                    bajas_ctx[s][:] = 1 + params.beta_bajas.get(s, 0.0) * (e_full / e_disp - 1)
                    ctx[s] = ctx[s] * bajas_ctx[s]
            # Puntos: cuanto cambia su parte del equipo sin los ausentes (ya va
            # en `cuota`; aqui solo se mide, para explicarlo).
            base_full = tf["points"].fillna(T.liga["points"]).values * mf
            parte_full = dict(zip(full_ids, base_full / base_full.sum()))
            bajas_ctx["points"] = np.array([
                cuota[k] / parte_full[a] if parte_full.get(a, 0) > 0 else 1.0
                for k, a in enumerate(ids)
            ])

        quienes = jugadores if jugadores is not None else _rotacion(dict(zip(ids, m)))
        col = {a: k for k, a in enumerate(ids)}
        for a in quienes:
            if a not in col:
                continue
            k = col[a]
            res = {}
            for s in STATS:
                mu = np.maximum(media[s][:, k], 1e-9)
                if prom is not None and a in prom.index:
                    w = params.mezcla[s]
                    base = float(mu.mean())
                    objetivo = w[0] * base + w[1] * prom.at[a, ("temporada", s)] + w[2] * prom.at[a, ("ult10", s)]
                    if base > 0 and objetivo == objetivo:
                        mu = mu * max(objetivo, 0.05) / base
                mu = mu * ctx[s][k]
                phi = params.dispersion[s]
                if phi > 1.0001:
                    lam = rng.gamma(mu / (phi - 1), phi - 1)
                else:
                    lam = mu
                res[s] = rng.poisson(lam)
            res["minutos"] = ms[:, k]
            res["info"] = {
                "grupo": grupos[k],
                "por_grupo": sorted(por_grupo),
                "rival": {s: float(rival_ctx[s][k]) for s in STATS},
                "bajas": {s: float(bajas_ctx[s][k]) for s in STATS},
                "minutos": float(m[k]),
                "minutos_completo": float(m_full[k]) if m_full is not None else None,
            }
            out[a] = res
    return out


def _escalera(valores: np.ndarray, ancho: int) -> dict:
    """P(over) en lineas .5 de uno en uno: {"desde": 9.5, "p": [0.99, 0.97, ...]}.

    Compacta a proposito: son 6 estadisticas por 16 jugadores por partido, y
    como diccionario linea -> probabilidad el archivo pasaba de 1 MB.
    """
    centro = float(np.median(valores))
    base = np.floor(centro) + 0.5
    lineas = np.arange(base - ancho, base + ancho + 1, 1.0)
    lineas = lineas[lineas > 0]
    s = np.sort(valores)
    n = len(s)
    p = [round(float(n - np.searchsorted(s, L, side="right")) / n, 3) for L in lineas]
    # Sin las lineas con menos de 0.5% de un lado: no le sirven a nadie. Como
    # P(over) baja con la linea, lo que queda es un tramo seguido.
    quedan = [i for i, x in enumerate(p) if 0.005 <= x <= 0.995]
    if not quedan:
        return {"desde": float(lineas[0]), "p": []}
    i, j = quedan[0], quedan[-1] + 1
    return {"desde": float(lineas[i]), "p": p[i:j]}


# Abanico por estadistica: lo bastante ancho para cualquier linea de casa.
ANCHO = {"points": 12, "reb": 6, "assists": 6, "pra": 15, "pr": 12, "pa": 12}
NOMBRE = {"points": "puntos", "reb": "rebotes", "assists": "asistencias",
          "pra": "pra", "pr": "puntos_rebotes", "pa": "puntos_asistencias"}


def resumir(sims: dict[str, np.ndarray]) -> dict:
    """Media, mediana, rango 80% y escalera de over por estadistica."""
    valores = {s: sims[s] for s in STATS}
    for c, partes in COMBOS.items():
        valores[c] = sum(sims[p] for p in partes)
    out = {"minutos": round(float(np.mean(sims["minutos"])), 1)}
    for clave, v in valores.items():
        out[NOMBRE[clave]] = {
            "media": round(float(v.mean()), 2),
            "mediana": float(np.median(v)),
            "p10": float(np.percentile(v, 10)),
            "p90": float(np.percentile(v, 90)),
            "overs": _escalera(v, ANCHO[clave]),
        }
    return out


# Desde cuanto vale la pena decirlo: debajo de esto es ruido para el lector.
UMBRAL_INSIGHT = {"points": 1.5, "reb": 0.8, "assists": 0.6}
CORTO = {"points": "pts", "reb": "reb", "assists": "ast"}
NOMBRE_LARGO = {"points": "puntos", "reb": "rebotes", "assists": "asistencias"}
# Frases completas: "DET permite pocas asistencias a los guardias (−0.7 ast)".
MUCHOS = {"points": "muchos puntos", "reb": "muchos rebotes", "assists": "muchas asistencias"}
POCOS = {"points": "pocos puntos", "reb": "pocos rebotes", "assists": "pocas asistencias"}


def _signo(x: float, fmt: str = ".1f") -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x):{fmt}}"


def insight(info: dict, medias: dict[str, float], rival: str, ausente: str | None = None,
            en_duda: bool = False) -> str | None:
    """La frase corta que explica lo que mas mueve el prop hoy, o None.

    Compite lo que suma la defensa rival contra su grupo, lo que suman los
    companeros fuera y los minutos de mas por bajas; gana el mas grande en
    relacion a su umbral. Si nada pasa el umbral, no se dice nada.
    """
    if en_duda:
        return "En duda: si no juega, la apuesta se anula"
    candidatos: list[tuple[float, str]] = []
    etiqueta = ROLES.get(info.get("grupo")) or POSICIONES.get(info.get("grupo"))
    for s in STATS:
        mu = medias[s]
        f = info["rival"][s]
        efecto = mu * (1 - 1 / f) if f > 0 else 0.0
        if abs(efecto) >= UMBRAL_INSIGHT[s]:
            cuanto = (MUCHOS if efecto > 0 else POCOS)[s]
            a_quien = f" a los {etiqueta}" if s in info.get("por_grupo", ()) and etiqueta else ""
            texto = f"{rival} permite {cuanto}{a_quien} ({_signo(efecto)} {CORTO[s]})"
            candidatos.append((abs(efecto) / UMBRAL_INSIGHT[s], texto))
        # En puntos la subida por bajas no predijo nada en el backtest (acierta
        # la direccion 47%), asi que no se usa para explicar.
        b = info["bajas"][s]
        efecto = mu * (1 - 1 / b) if b > 0 else 0.0
        if ausente and s != "points" and efecto >= UMBRAL_INSIGHT[s]:
            candidatos.append((efecto / UMBRAL_INSIGHT[s],
                               f"Sin {ausente} le tocan más {NOMBRE_LARGO[s]} ({_signo(efecto)} {CORTO[s]})"))
    extra = info["minutos"] - (info.get("minutos_completo") or info["minutos"])
    if ausente and extra >= 4:
        candidatos.append((extra / 4, f"Sin {ausente} juega más minutos (+{extra:.0f} min)"))
    if not candidatos:
        return None
    return max(candidatos)[1][:80]


def jugadores_disponibles(jugadores: pd.DataFrame, game_id: int) -> pd.DataFrame:
    """Para el backtest: quienes estaban disponibles en ese partido."""
    g = jugadores[jugadores.game_id == game_id]
    return g[~no_disponible(g.did_not_play, g.reason)]
