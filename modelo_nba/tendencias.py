"""Tendencias de defensa contra posicion: "DET permite los mas rebotes a SG".

Es el formato que se ve en redes y se publica asi, con su jugador. Es
descriptivo: dice lo que cada defensa ha permitido, no lo que va a pasar. En
la prueba a ciegas de 2025-26 estos rankings no predijeron puntos ni rebotes
mejor que el azar (docs/PROPS.md); la proyeccion solo usa la parte que si
valido, asistencias contra la posicion.

ESPN solo da G, F o C. Para las cinco posiciones, los guardias se separan en
PG (los que mas asisten) y SG, y los aleros en PF (los que mas rebotean) y SF,
con sus tasas del ultimo ano, partiendo los minutos de cada grupo a la mitad.
"""

from __future__ import annotations

import pandas as pd

# Columna del box score -> nombre que se publica.
STATS = {
    "points": "puntos",
    "reb": "rebotes",
    "assists": "asistencias",
    "three_point_field_goals_made": "triples",
}
POSICIONES = ("PG", "SG", "SF", "PF", "C")
RANGO_MAXIMO = 5  # solo se publican las 5 defensas que mas permiten
POR_JUGADOR = 3  # lineas por jugador
MINIMO_PARTIDOS = 5  # menos que esto en la temporada: se usa la anterior
# El alero de ESPN que juega de centro (Wembanyama): rebotes y tapones por
# 100 posesiones en cancha.
CORTE_C_REB, CORTE_C_TAP = 14.0, 3.5


def _mediana_ponderada(x: pd.Series, w: pd.Series) -> float:
    if x.empty:
        return float("nan")
    orden = x.sort_values()
    acumulado = w.reindex(orden.index).cumsum()
    return float(orden[acumulado > acumulado.iloc[-1] / 2].iloc[0])


def posiciones5(tabla: pd.DataFrame, antes_de, generales: pd.Series | None = None) -> pd.Series:
    """PG/SG/SF/PF/C de cada jugador, a partir de G/F/C y sus tasas.

    `generales` (G/F/C) completa a quien no tiene posicion en el historico,
    como un novato con la del roster de ESPN.
    """
    base = tabla.dropna(subset=["posicion"]).groupby("athlete_id").posicion.last() \
        if "posicion" in tabla else pd.Series(dtype=object)
    if generales is not None:
        base = pd.concat([generales.dropna(), base])
        base = base[~base.index.duplicated(keep="last")]
    t = tabla[(tabla.fecha < antes_de) & (tabla.fecha >= antes_de - pd.Timedelta(days=365))]
    g = t.groupby("athlete_id")[["pos", "assists", "reb", "blocks"]].sum()
    g = g[g.pos >= 300]
    por100 = g[["assists", "reb", "blocks"]].div(g.pos, axis=0) * 100
    # Los cortes parten los MINUTOS de guardias y de aleros a la mitad, como en
    # una alineacion (un PG y un SG, un SF y un PF). Por jugador, la mitad de la
    # liga salia de una sola posicion y el ranking de las otras era ruido.
    etiqueta = base.reindex(por100.index)
    guardias, aleros = etiqueta == "G", etiqueta == "F"
    corte_pg = _mediana_ponderada(por100.assists[guardias], g.pos)
    corte_pf = _mediana_ponderada(por100.reb[aleros], g.pos)
    out = {}
    for a, p in base.items():
        r = por100.loc[a] if a in por100.index else None
        if p == "G":
            out[a] = "PG" if r is not None and r.assists >= corte_pg else "SG"
        elif p == "F":
            if r is not None and r.reb >= CORTE_C_REB and r.blocks >= CORTE_C_TAP:
                out[a] = "C"
            else:
                out[a] = "PF" if r is not None and r.reb >= corte_pf else "SF"
        elif p == "C":
            out[a] = "C"
    return pd.Series(out, dtype=object)


def _permitido(t: pd.DataFrame) -> pd.DataFrame:
    """Promedio por partido que cada defensa permite a cada posicion."""
    total = t.groupby(["rival", "p5"])[list(STATS)].sum().reset_index()
    juegos = t.groupby("rival").game_id.nunique().rename("juegos").reset_index()
    total = total.merge(juegos, on="rival")
    total[list(STATS)] = total[list(STATS)].div(total.juegos, axis=0)
    return total.drop(columns="juegos").set_index(["rival", "p5"])


def rankings(tabla: pd.DataFrame, antes_de, temporada: int, pos5: pd.Series) -> dict:
    """Por ventana: valor y lugar (1 = la que mas permite) de cada defensa,
    posicion y estadistica. Solo temporada regular."""
    t = tabla[(tabla.fecha < antes_de) & (tabla.season_type == 2)].copy()
    t["p5"] = t.athlete_id.map(pos5)
    t = t.dropna(subset=["p5"])

    actual = t[t.season == temporada]
    jugados = actual.groupby("rival").game_id.nunique()
    if len(jugados) and jugados.median() >= MINIMO_PARTIDOS:
        temp, etiqueta = actual, "Temporada"
    else:
        temp, etiqueta = t[t.season == temporada - 1], "Temporada pasada"

    # Ultimos 7 de cada defensa, de cualquier temporada.
    juegos = t[["rival", "game_id", "fecha"]].drop_duplicates()
    ultimos = juegos.sort_values("fecha").groupby("rival").tail(7)
    ult7 = t.merge(ultimos[["rival", "game_id"]], on=["rival", "game_id"])

    out = {}
    for clave, datos, nombre in (("temporada", temp, etiqueta), ("ultimos7", ult7, "Últimos 7")):
        if datos.empty:
            continue
        v = _permitido(datos)
        lugar = v.groupby(level="p5").rank(ascending=False, method="min")
        out[clave] = {"nombre": nombre, "valor": v, "lugar": lugar}
    return out


def del_partido(R: dict, casa: dict, visita: dict) -> dict[int, list[dict]]:
    """Las lineas de un partido, como en redes, pegadas a su jugador.

    `casa`/`visita`: {"abbr", "team_id", "rotacion": [(athlete_id, posicion5)]}
    con la rotacion ordenada por minutos. Cada defensa se cruza con la
    rotacion del rival: por posicion, la linea va al jugador con mas minutos.
    Devuelve athlete_id -> sus lineas (a lo sumo POR_JUGADOR, las de mejor
    lugar primero).
    """
    por_jugador: dict[int, list[dict]] = {}
    for clave, r in R.items():
        for defensa, ataque in ((casa, visita), (visita, casa)):
            tid = defensa["team_id"]
            primero: dict[str, int] = {}
            for a, p in ataque["rotacion"]:
                if p and p not in primero:
                    primero[p] = a
            for p, a in primero.items():
                if (tid, p) not in r["lugar"].index:
                    continue
                for col, stat in STATS.items():
                    lugar = int(r["lugar"].at[(tid, p), col])
                    if lugar <= RANGO_MAXIMO:
                        por_jugador.setdefault(a, []).append({
                            "defensa": defensa["abbr"], "lugar": lugar, "stat": stat,
                            "posicion": p, "ventana": clave, "nombre_ventana": r["nombre"],
                            "valor": round(float(r["valor"].at[(tid, p), col]), 1),
                        })
    for a in por_jugador:
        por_jugador[a] = sorted(por_jugador[a], key=lambda x: (x["lugar"], x["ventana"] != "temporada"))[:POR_JUGADOR]
    return por_jugador
