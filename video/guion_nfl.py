"""Guion del video para un partido de NFL. Mismas escenas que NBA, otro idioma:
yardas, touchdowns y quarterbacks. Lee el contrato de `data/video/<game_id>.json`
(ver `contrato-nfl.md`).

    python guion_nfl.py datos.json metricas.json guion.json
"""

from __future__ import annotations

import json
import sys

from equipos import equipo
from guion import MARCA, Narracion, _apellido, _fecha, pct
from numeros import decir, miles

# Estadistica principal por posicion y como se dice.
PRINCIPAL = {"QB": "pass_yds", "RB": "rush_yds", "FB": "rush_yds"}
HIZO = {"pass_yds": "lanzó para", "rush_yds": "corrió para", "rec_yds": "atrapó"}
HACE = {"pass_yds": "lanza para", "rush_yds": "corre para", "rec_yds": "atrapa", "pass_td": "lanza", "td": "anota"}
ROTULO = {"pass_yds": "YARDAS POR PASE", "rush_yds": "YARDAS POR TIERRA", "rec_yds": "YARDAS POR RECEPCIÓN"}
CORTO = {"pass_yds": "YDS PASE", "rush_yds": "YDS TIERRA", "rec_yds": "YDS REC"}


def _stat(j: dict) -> str:
    return j.get("mejor", {}).get("stat") or PRINCIPAL.get(j.get("posicion", ""), "rec_yds")


# Cuanto es "mucho" por estadistica, para comparar un QB con un receptor.
ESCALA = {"pass_yds": 100.0, "rush_yds": 40.0, "rec_yds": 40.0}
MINIMO = {"pass_yds": 150.0, "rush_yds": 30.0, "rec_yds": 30.0}


def _rareza(j: dict) -> float:
    """Que tan lejos de su promedio quedo su mejor partido. Los que casi no
    tocan el balon no cuentan: nadie los conoce y su promedio es ruido."""
    s = _stat(j)
    media = j["media"].get(s, 0.0)
    if media < MINIMO[s]:
        return 0.0
    return (j["mejor"]["valor"] - media) / ESCALA[s]


def _umbral(js: list[dict], stat: str, meta: float = 0.25) -> str | None:
    comunes = set.intersection(*(set(j["sobre"].get(stat, {})) for j in js)) if js else set()
    if not comunes:
        return None
    return min(comunes, key=lambda u: abs(max(j["sobre"][stat][u] for j in js) - meta))


def _tarjeta(j: dict, eq: dict, lineas: list[tuple[str, str]]) -> dict:
    return {"athlete_id": j["athlete_id"], "jugador": j["jugador"], "color": eq["color"],
            "lineas": [{"valor": v, "etiqueta": e} for v, e in lineas]}


def _evento_voz(e: dict, corto: bool) -> tuple[str, str]:
    """Texto en pantalla y dicho para "cuando X <hace algo>"."""
    s, u = e["stat"], e["umbral"]
    if s == "td":
        t = "anota" if u <= 1 else f"anota {u} veces"
        return t, "anota" if u <= 1 else f"anota {decir(u)} veces"
    if s == "pass_td":
        return f"lanza {u} touchdowns", f"lanza {decir(u)} touchdowns"
    unidad = "" if corto else " yardas"
    return f"{HACE[s]} {u}{unidad}", f"{HACE[s]} {decir(u)}{unidad}"


def _normalizar(d: dict) -> dict:
    """Acepta las variantes de nombre que escribe el simulador NFL."""
    m = d["margen"]
    for k, rotulo, umbral in (("una_posesion", "POR UNA POSESIÓN", 8), ("cerrados_8", "POR UNA POSESIÓN", 8),
                              ("cerrados_7", "POR UN TOUCHDOWN O MENOS", 7), ("cerrados_3", "POR UN GOL DE CAMPO", 3)):
        if k in m:
            m["_cerrados"], m["_rotulo"], m["_umbral"] = m[k], rotulo, umbral
            break
    for lado in ("home", "away"):
        for j in d["jugadores"][lado]:
            j.setdefault("athlete_id", j.get("espn_id"))
            j["athlete_id"] = int(j["athlete_id"])
            if "anytime_td" in j:
                j["sobre"].setdefault("td", {}).setdefault("1", j["anytime_td"])
            j["sobre"] = {s: {str(u): p for u, p in us.items()} for s, us in j["sobre"].items()}
            mejor = j["mejor"]
            if "valor" not in mejor:  # viene como {"rec_yds": 260, "gano": true}
                s = mejor.get("stat") or next(k for k in (PRINCIPAL.get(j.get("posicion", ""), "rec_yds"),
                                                          "rec_yds", "rush_yds", "pass_yds") if k in mejor)
                mejor["stat"], mejor["valor"] = s, mejor[s]
            mejor["valor"] = int(round(mejor["valor"]))
    return d


def construir(d: dict, metricas: dict | None = None) -> dict:
    d = _normalizar(d)
    n = d["simulaciones"]
    eq = {lado: equipo(d["equipos"][lado]["abbr"], "nfl") for lado in ("home", "away")}
    # Dos equipos del mismo tono no se distinguen en las graficas.
    if eq["home"]["color"].lower() == eq["away"]["color"].lower():
        eq["away"]["color"] = eq["away"]["color2"]
    jug = d["jugadores"]
    lado_de = {j["athlete_id"]: lado for lado in jug for j in jug[lado]}
    todos = jug["home"] + jug["away"]
    favorito = "home" if d["victorias"]["home"] >= d["victorias"]["away"] else "away"
    otro = "away" if favorito == "home" else "home"
    p_gana = {lado: d["victorias"][lado] / n for lado in ("home", "away")}
    escenas = []

    # 1. Gancho: el partido mas fuera de serie; de los mas raros, mejor uno que acabo en derrota.
    # Primero, una actuacion enorme que acabo en derrota (el numero mas
    # grande llama mas); si no hay, la mas fuera de serie.
    derrotas = [j for j in todos if not j["mejor"]["gano"] and _rareza(j) >= 2.0]
    gancho = max(derrotas, key=lambda j: j["mejor"]["valor"]) if derrotas else max(todos, key=_rareza)
    lg, sg = lado_de[gancho["athlete_id"]], _stat(gancho)
    nar = Narracion().t("En una de nuestras").n(n).t("simulaciones,").t(f"{gancho['jugador']} {HIZO[sg]}") \
        .n(gancho["mejor"]["valor"], cue="numero").t("yardas...")
    remate = None
    if not gancho["mejor"]["gano"]:
        remate = "Y PERDIERON"
        nar.t(f"y los {eq[lg]['apodo']} perdieron.", cue="remate")
    escenas.append({"tipo": "heroe", "props": {
        "athlete_id": gancho["athlete_id"], "jugador": gancho["jugador"], "color": eq[lg]["color"],
        "desde": int(round(gancho["media"].get(sg, 0))), "hasta": gancho["mejor"]["valor"],
        "etiqueta": ROTULO[sg], "sub": f"{gancho['jugador']} · EN 1 DE {miles(n)} SIMULACIONES",
        "remate": remate}, "narracion": nar.trozos})

    # 2. Presentacion.
    nar = Narracion().t(f"Simulamos {eq['away']['apodo']} contra {eq['home']['apodo']}").n(n).t("veces.").t("Esto pasó.")
    escenas.append({"tipo": "titulo", "props": {
        "titulo": "SIMULAMOS", "sub": f"{eq['away']['apodo']} @ {eq['home']['apodo']} {miles(n)} VECES"},
        "narracion": nar.trozos})

    # 3. Record. Las versiones del modelo se traslapan en los mismos partidos:
    # se usa la que mas partidos tiene calificados.
    if metricas:
        mls = [v["markets"]["moneyline"] for v in metricas["versions"] if v.get("markets", {}).get("moneyline")]
        if mls:
            ml = max(mls, key=lambda m: m["n"])
            total, aciertos = ml["n"], int(round(ml["n"] * ml["hit_rate"]))
            nar = Narracion().t("Antes, un dato:").t("el modelo acertó al ganador en") \
                .n(aciertos, cue="numero").t("de").n(total).t("partidos.")
            escenas.append({"tipo": "record", "props": {
                "aciertos": aciertos, "total": total, "pct": pct(aciertos / total)}, "narracion": nar.trozos})

    # 4. Resultado.
    nar = Narracion().t("¿Quién gana?").t(f"Los {eq[favorito]['apodo']} se llevan el", cue="cuenta") \
        .p(p_gana[favorito], fin=".").t(f"Los {eq[otro]['apodo']}, el").p(p_gana[otro], fin=".") \
        .t(f"Van los {eq[favorito]['apodo']}.", cue="veredicto")
    escenas.append({"tipo": "resultado", "props": {
        "titulo": f"{miles(n)} PARTIDOS DESPUÉS",
        "victorias": {"home": d["victorias"]["home"], "away": d["victorias"]["away"]}, "muestra": d["muestra"],
        "veredicto": f"{eq[favorito]['apodo']} GANAN EL {pct(p_gana[favorito])}%", "favorito": favorito},
        "narracion": nar.trozos})

    # 5. Que tan cerrado.
    m, mm = d["margen"], d["marcador_medio"]
    alto, bajo = sorted((round(mm["home"]), round(mm["away"])), reverse=True)
    nar = Narracion().t("Marcador promedio:").n(alto, cue="marcador").t("a").n(bajo, sufijo=".") \
        .t("El", cue="cerrados").p(m["_cerrados"]).t(f"se define {m['_rotulo'].lower()},") \
        .t("y el", cue="ot").p(m["tiempo_extra"]).t("va a tiempo extra.")
    escenas.append({"tipo": "cerrado", "props": {
        "titulo": "¿QUÉ TAN CERRADO?", "cuentas": m["cuentas"], "desde": m["desde"], "ancho": m["ancho"],
        "marcador": {"home": round(mm["home"]), "away": round(mm["away"])},
        "cerrados": pct(m["_cerrados"]), "ot": pct(m["tiempo_extra"]),
        "etiqueta_cerrados": m["_rotulo"], "umbral_cerrado": m["_umbral"]}, "narracion": nar.trozos})

    # 6. Duelo de quarterbacks.
    def _qb(lado):
        qbs = [j for j in jug[lado] if j.get("posicion") == "QB"]
        return max(qbs or jug[lado], key=lambda j: j["media"].get("pass_yds", 0))
    a, b = _qb(favorito), _qb(otro)
    u = _umbral([a, b], "pass_yds")
    nar = Narracion().t("Duelo de quarterbacks:")
    for k, j in enumerate((a, b)):
        nar.t(f"{j['jugador']} promedia", cue=f"tarjeta{k}").n(round(j["media"]["pass_yds"]))
        if k == 0:
            nar.t("yardas por pase")
        if u:
            nar.t(f"y pasa de {u} en el" if k == 0 else f"y llega a {u} en el",
                  f"y {'pasa de' if k == 0 else 'llega a'} {decir(int(u))} en el").p(j["sobre"]["pass_yds"][u], fin=".")
    escenas.append({"tipo": "tarjetas", "props": {"titulo": "DUELO DE QUARTERBACKS", "tarjetas": [
        _tarjeta(j, eq[lado], [(f"{j['media']['pass_yds']:.0f} YDS", "POR PASE, PROMEDIO POR SIMULACIÓN")]
                 + ([(f"{pct(j['sobre']['pass_yds'][u])}%", f"DE LAS SIMS CON {u}+ YARDAS")] if u else []))
        for j, lado in ((a, favorito), (b, otro))]}, "narracion": nar.trozos})

    # 7. Las armas: por lado, el que mas yardas produce sin ser el QB.
    def _arma(lado, qb):
        resto = [j for j in jug[lado] if j["athlete_id"] != qb["athlete_id"]] or jug[lado]
        return max(resto, key=lambda j: j["media"].get("rush_yds", 0) + j["media"].get("rec_yds", 0))
    nar = Narracion()
    tarjetas = []
    for k, (lado, qb) in enumerate(((favorito, a), (otro, b))):
        j = _arma(lado, qb)
        s = "rush_yds" if j["media"].get("rush_yds", 0) > j["media"].get("rec_yds", 0) else "rec_yds"
        p_td = j["sobre"].get("td", {}).get("1")
        ux = _umbral([j], s, 0.30)
        p_yd = j["sobre"][s][ux] if ux else None
        # Se dice lo mas llamativo; la tarjeta ensena las dos cosas.
        if p_yd is not None and (p_td is None or k == 1 or p_yd >= p_td):
            nar.t(f"{j['jugador']} pasa de {ux} yardas en el", f"{j['jugador']} pasa de {decir(int(ux))} yardas en el",
                  cue=f"tarjeta{k}").p(p_yd, fin=".")
        else:
            nar.t(f"{j['jugador']} anota en el", cue=f"tarjeta{k}").p(p_td, fin=".")
        lineas = []
        if p_td is not None:
            lineas.append((f"{pct(p_td)}%", "DE LAS SIMS CON TOUCHDOWN"))
        if p_yd is not None:
            lineas.append((f"{pct(p_yd)}%", f"DE LAS SIMS CON {ux}+ {CORTO[s]}"))
        if not lineas:
            lineas.append((f"{j['media'][s]:.0f} YDS", "PROMEDIO POR SIMULACIÓN"))
        tarjetas.append(_tarjeta(j, eq[lado], lineas))
    escenas.append({"tipo": "tarjetas", "props": {"titulo": "LAS ARMAS", "tarjetas": tarjetas},
                    "narracion": nar.trozos})

    # 8. El partido mas raro del otro equipo.
    lr = "away" if lg == "home" else "home"
    raro = max(jug[lr], key=_rareza)
    sr = _stat(raro)
    # Si el simulador manda el percentil 99 en vez del maximo, no es "el mas
    # raro": es su noche grande, la que pasa una de cada cien veces.
    cada = raro["mejor"].get("una_de_cada")
    nar = Narracion().t(f"La noche grande de los {eq[lr]['apodo']}:" if cada else f"El partido más raro de los {eq[lr]['apodo']}:") \
        .t(f"{raro['jugador']} con").n(raro["mejor"]["valor"], cue="numero").t("yardas.")
    if cada:
        nar.t("Pasa una de cada").n(cada).t("veces.")
    nar.t("Su promedio es", cue="promedio").n(round(raro["media"].get(sr, 0)), sufijo=".")
    escenas.append({"tipo": "heroe", "props": {
        "titulo": "LA NOCHE GRANDE" if cada else "EL PARTIDO MÁS RARO", "athlete_id": raro["athlete_id"], "jugador": raro["jugador"],
        "color": eq[lr]["color"], "desde": int(round(raro["media"].get(sr, 0))), "hasta": raro["mejor"]["valor"],
        "etiqueta": ROTULO[sr],
        "sub": f"{raro['jugador']} · 1 DE CADA {cada} SIMS" if cada else f"{raro['jugador']} · SU MEJOR EN {miles(n)} SIMS",
        "pie": f"PROMEDIO: {raro['media'].get(sr, 0):.0f} YDS", "remate": None}, "narracion": nar.trozos})

    # 9. Que lo decide.
    nar = Narracion().t("¿Qué lo decide?")
    medidores = []
    for k, lado in enumerate((favorito, otro)):
        opciones = [(j, e) for j in jug[lado] if j["athlete_id"] != gancho["athlete_id"]
                    for e in j.get("eventos", []) if e["p_evento"] >= 0.15 and e["empuje"] > 0]
        if not opciones:
            continue
        j, e = max(opciones, key=lambda x: x[1]["empuje"] * x[1]["p_evento"] ** 0.5)
        visto, dicho = _evento_voz(e, corto=False)
        nar.t(f"Cuando {_apellido(j['jugador'])} {visto},", f"Cuando {_apellido(j['jugador'])} {dicho},",
              cue=f"medidor{k}").t(f"los {eq[lado]['apodo']} ganan el").p(e["p_gana"], cue=f"sube{k}", fin=".")
        medidores.append({"athlete_id": j["athlete_id"], "jugador": _apellido(j["jugador"]),
                          "evento": e["texto"].upper(), "color": eq[lado]["color"],
                          "equipo": f"{eq[lado]['apodo']} GANAN", "base": pct(p_gana[lado]), "pct": pct(e["p_gana"])})
    if medidores:
        escenas.append({"tipo": "decide", "props": {"titulo": "¿QUÉ LO DECIDE?", "medidores": medidores},
                        "narracion": nar.trozos})

    # 10. Cierre.
    nar = Narracion().t(f"¿{eq['away']['apodo']} o {eq['home']['apodo']}?").t("¿Con quién vas?", cue="pregunta") \
        .t("Déjalo en los comentarios.", cue="comenta").t("Mañana revisamos.")
    escenas.append({"tipo": "cierre", "props": {"titulo": "¿CON QUIÉN VAS?", "linea1": "COMENTA TU PICK",
                                              "linea2": "RESULTADO MAÑANA"}, "narracion": nar.trozos})

    return {"game_id": d["game_id"], "liga": "nfl", "marca": MARCA, "simulaciones": n,
            "fecha": _fecha(d["starts_at"]), "equipos": eq, "cinta": d["cinta"], "escenas": escenas}


if __name__ == "__main__":
    datos = json.load(open(sys.argv[1]))
    met = json.load(open(sys.argv[2])) if len(sys.argv) > 3 and sys.argv[2] != "-" else None
    g = construir(datos, met)
    json.dump(g, open(sys.argv[-1], "w"), ensure_ascii=False, indent=1)
    for e in g["escenas"]:
        print(f"[{e['tipo']}]", " ".join(t["texto"] for t in e["narracion"]))
