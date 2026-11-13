"""Del JSON del simulador al guion: que historias se cuentan y con que palabras.

Todo es determinista y sale de `data/video/<game_id>.json`: ningun numero se
escribe a mano. Cada escena lleva lo que se ve (`props`) y lo que se dice
(`narracion`), en trozos. Un trozo puede traer `cue`: el nombre de la animacion
que arranca cuando la voz llega a el.

    python guion.py ../data/video/401909976.json ../data/edgebook-metrics.json guion.json
"""

from __future__ import annotations

import json
import sys

from equipos import equipo
from numeros import decir, miles

MARCA = "EDGEBOOK"


def pct(p: float) -> int:
    return int(round(p * 100))


class Narracion:
    """Trozos de texto: lo que se lee en pantalla y como lo dice la voz."""

    def __init__(self):
        self.trozos = []

    def t(self, texto: str, voz: str | None = None, cue: str | None = None):
        self.trozos.append({"texto": texto, "voz": voz or texto, "cue": cue})
        return self

    def n(self, n: int, cue: str | None = None, sufijo: str = "", voz_sufijo: str = ""):
        return self.t(miles(n) + sufijo, decir(n) + voz_sufijo, cue)

    def p(self, p: float, cue: str | None = None, fin: str = ""):
        return self.t(f"{pct(p)}%{fin}", f"{decir(pct(p))} por ciento{fin}", cue)


def _fecha(inicio: str) -> str:
    """Dia del partido en hora del Este, como "12 NOV"."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    t = datetime.fromisoformat(inicio.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
    return f"{t.day} {'ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC'.split()[t.month - 1]}"


def _apellido(nombre: str) -> str:
    partes = nombre.split()
    return " ".join(partes[1:]) if len(partes) > 1 else nombre


def _umbral_duelo(a: dict, b: dict) -> str:
    """El umbral de puntos que el mejor de los dos pasa mas o menos 1 de cada 4."""
    return min(a["sobre"]["points"], key=lambda u: abs(max(a["sobre"]["points"][u], b["sobre"]["points"][u]) - 0.25))


def _tarjeta(j: dict, eq: dict, lineas: list[tuple[str, str]]) -> dict:
    return {"athlete_id": j["athlete_id"], "jugador": j["jugador"], "color": eq["color"],
            "lineas": [{"valor": v, "etiqueta": e} for v, e in lineas]}


def construir(d: dict, metricas: dict | None = None) -> dict:
    n = d["simulaciones"]
    eq = {lado: equipo(d["equipos"][lado]["abbr"]) for lado in ("home", "away")}
    jug = d["jugadores"]
    lado_de = {j["athlete_id"]: lado for lado in jug for j in jug[lado]}
    todos = jug["home"] + jug["away"]
    favorito = "home" if d["victorias"]["home"] >= d["victorias"]["away"] else "away"
    otro = "away" if favorito == "home" else "home"
    p_gana = {lado: d["victorias"][lado] / n for lado in ("home", "away")}
    escenas = []

    # 1. Gancho: el partido mas anotador de todas las simulaciones. Si entre
    # los mas altos hay uno que acabo en derrota, ese: es mejor historia.
    tope = max(j["mejor"]["points"] for j in todos)
    candidatos = [j for j in todos if j["mejor"]["points"] >= tope - 5]
    gancho = max(candidatos, key=lambda j: (not j["mejor"]["gano"], j["mejor"]["points"]))
    lg = lado_de[gancho["athlete_id"]]
    nar = Narracion().t("En una de nuestras").n(n).t("simulaciones,").t(f"{gancho['jugador']} metió") \
        .n(gancho["mejor"]["points"], cue="numero").t("puntos...")
    remate = None
    if not gancho["mejor"]["gano"]:
        remate = "Y PERDIERON"
        nar.t(f"y {eq[lg]['ciudad']} perdió.", cue="remate")
    escenas.append({"tipo": "heroe", "props": {
        "athlete_id": gancho["athlete_id"], "jugador": gancho["jugador"], "color": eq[lg]["color"],
        "desde": int(round(gancho["media"]["points"])), "hasta": gancho["mejor"]["points"],
        "etiqueta": "PUNTOS", "sub": f"{gancho['jugador']} · EN 1 DE {miles(n)} SIMULACIONES",
        "remate": remate}, "narracion": nar.trozos})

    # 2. Presentacion.
    nar = Narracion().t(f"Simulamos {eq['away']['apodo']} contra {eq['home']['apodo']}").n(n).t("veces.") \
        .t("Esto pasó.")
    escenas.append({"tipo": "titulo", "props": {
        "titulo": "SIMULAMOS", "sub": f"{eq['away']['apodo']} @ {eq['home']['apodo']} {miles(n)} VECES"},
        "narracion": nar.trozos})

    # 3. Credibilidad: el record del modelo, calificado contra marcadores reales.
    if metricas:
        # Todas las versiones del modelo en la temporada, no solo la ultima.
        mls = [v["markets"]["moneyline"] for v in metricas["versions"] if v.get("markets", {}).get("moneyline")]
        total = sum(ml["n"] for ml in mls)
        aciertos = int(round(sum(ml["n"] * ml["hit_rate"] for ml in mls)))
        nar = Narracion().t("Antes, un dato:").t("el modelo acertó al ganador en") \
            .n(aciertos, cue="numero").t("de").n(total).t("partidos.")
        escenas.append({"tipo": "record", "props": {
            "aciertos": aciertos, "total": total, "pct": pct(aciertos / total)}, "narracion": nar.trozos})

    # 4. Resultado.
    # Los conteos exactos se ven en pantalla; la voz dice solo porcentajes,
    # que en palabras son mucho mas cortos que "once mil seiscientos...".
    nar = Narracion().t("¿Quién gana?").t(f"{eq[favorito]['ciudad']} se lleva el", cue="cuenta") \
        .p(p_gana[favorito], fin=".").t(f"{eq[otro]['ciudad']}, el").p(p_gana[otro], fin=".") \
        .t(f"Van los {eq[favorito]['apodo']}.", cue="veredicto")
    escenas.append({"tipo": "resultado", "props": {
        "titulo": f"{miles(n)} PARTIDOS DESPUÉS", "victorias": d["victorias"], "muestra": d["muestra"],
        "veredicto": f"{eq[favorito]['apodo']} GANAN EL {pct(p_gana[favorito])}%", "favorito": favorito},
        "narracion": nar.trozos})

    # 5. Que tan cerrado.
    m = d["margen"]
    mm = d["marcador_medio"]
    alto, bajo = sorted((round(mm["home"]), round(mm["away"])), reverse=True)
    nar = Narracion().t("Marcador promedio:").n(alto, cue="marcador").t("a").n(bajo, sufijo=".") \
        .t("El", cue="cerrados").p(m["cerrados_5"]).t("se define por cinco o menos,") \
        .t("y el", cue="ot").p(m["tiempo_extra"]).t("va a tiempo extra.")
    escenas.append({"tipo": "cerrado", "props": {
        "titulo": "¿QUÉ TAN CERRADO?", "cuentas": m["cuentas"], "desde": m["desde"], "ancho": m["ancho"],
        "marcador": {"home": round(mm["home"]), "away": round(mm["away"])},
        "cerrados": pct(m["cerrados_5"]), "ot": pct(m["tiempo_extra"])}, "narracion": nar.trozos})

    # 6. Duelo de anotadores: el que mas anota de cada lado.
    a = max(jug[favorito], key=lambda j: j["media"]["points"])
    b = max(jug[otro], key=lambda j: j["media"]["points"])
    u = _umbral_duelo(a, b)
    nar = Narracion().t("Duelo de anotadores:")
    for k, (j, lado) in enumerate(((a, favorito), (b, otro))):
        nar.t(f"{j['jugador']} promedia", cue=f"tarjeta{k}").n(round(j["media"]["points"])) \
            .t("puntos" if k == 0 else "") \
            .t(f"y pasa de {u} en el" if k == 0 else f"y llega a {u} en el", f"y {'pasa de' if k == 0 else 'llega a'} {decir(int(u))} en el") \
            .p(j["sobre"]["points"][u], fin=".")
    nar.trozos = [t for t in nar.trozos if t["texto"]]
    escenas.append({"tipo": "tarjetas", "props": {"titulo": "DUELO DE ANOTADORES", "tarjetas": [
        _tarjeta(j, eq[lado], [(f"{j['media']['points']:.0f} PTS", "PROMEDIO POR SIMULACIÓN"),
                               (f"{pct(j['sobre']['points'][u])}%", f"DE LAS SIMS CON {u}+ PUNTOS")])
        for j, lado in ((a, favorito), (b, otro))]}, "narracion": nar.trozos})

    # 7. Los que acompanan: por lado, el que mas doble-dobles firma (si es
    # creible) o el siguiente anotador con sus asistencias.
    def _segundo(lado, usado):
        resto = [j for j in jug[lado] if j["athlete_id"] != usado["athlete_id"]]
        dd = max(resto, key=lambda j: j["doble_doble"])
        if dd["doble_doble"] >= 0.30:
            return dd, "dd"
        return max(resto, key=lambda j: j["media"]["points"]), "pa"
    nar = Narracion()
    tarjetas = []
    for k, (lado, usado) in enumerate(((favorito, a), (otro, b))):
        j, modo = _segundo(lado, usado)
        if modo == "dd":
            nar.t(f"{j['jugador']} firma doble-doble en el", cue=f"tarjeta{k}").p(j["doble_doble"], fin=".")
            tarjetas.append(_tarjeta(j, eq[lado], [
                (f"{pct(j['doble_doble'])}%", "DE LAS SIMS CON DOBLE-DOBLE"),
                (f"{j['media']['points']:.0f} PTS · {j['media']['reb']:.0f} REB", "PROMEDIO POR SIMULACIÓN")]))
        else:
            nar.t(f"{j['jugador']} promedia", cue=f"tarjeta{k}").n(round(j["media"]["points"])).t("puntos y") \
                .n(round(j["media"]["assists"])).t("asistencias.")
            tarjetas.append(_tarjeta(j, eq[lado], [
                (f"{j['media']['points']:.0f} PTS · {j['media']['assists']:.0f} AST", "PROMEDIO POR SIMULACIÓN"),
                (f"{pct(j['sobre']['points']['20'])}%", "DE LAS SIMS CON 20+ PUNTOS")]))
    escenas.append({"tipo": "tarjetas", "props": {"titulo": "LOS QUE ACOMPAÑAN", "tarjetas": tarjetas},
                    "narracion": nar.trozos})

    # 8. El partido mas raro del otro equipo (el del gancho ya se conto).
    lr = "away" if lg == "home" else "home"
    raro = max(jug[lr], key=lambda j: j["mejor"]["points"])
    nar = Narracion().t(f"El partido más raro de {eq[lr]['ciudad']}:").t(f"{raro['jugador']} con") \
        .n(raro["mejor"]["points"], cue="numero").t("puntos") \
        .t("y").n(raro["mejor"]["reb"]).t("rebotes.").t("Su promedio es", cue="promedio") \
        .n(round(raro["media"]["points"]), sufijo=".")
    escenas.append({"tipo": "heroe", "props": {
        "titulo": "EL PARTIDO MÁS RARO", "athlete_id": raro["athlete_id"], "jugador": raro["jugador"],
        "color": eq[lr]["color"], "desde": int(round(raro["media"]["points"])), "hasta": raro["mejor"]["points"],
        "etiqueta": "PUNTOS", "sub": f"{raro['jugador']} · SU MEJOR EN {miles(n)} SIMS",
        "pie": f"PROMEDIO: {raro['media']['points']:.0f} PTS", "remate": None}, "narracion": nar.trozos})

    # 9. Que lo decide: por lado, el evento que mas empuja la victoria.
    nar = Narracion().t("¿Qué lo decide?")
    medidores = []
    for k, lado in enumerate((favorito, otro)):
        opciones = [(j, e) for j in jug[lado] if j["athlete_id"] != gancho["athlete_id"]
                    for e in j["eventos"] if e["p_evento"] >= 0.15 and e["empuje"] > 0]
        if not opciones:
            continue
        # Empuje pesado por que tan seguido pasa: un evento raro mueve mucho
        # el porcentaje pero casi nunca se va a ver.
        j, e = max(opciones, key=lambda x: x[1]["empuje"] * x[1]["p_evento"] ** 0.5)
        etiqueta = {"points": "puntos", "reb": "rebotes", "assists": "asistencias"}[e["stat"]]
        verbo = {"points": "mete", "reb": "baja", "assists": "reparte"}[e["stat"]]
        nar.t(f"Cuando {_apellido(j['jugador'])} {verbo} {e['umbral']} {etiqueta if k == 0 else ''}".strip()
              + (" o más," if k == 0 else ","),
              f"Cuando {_apellido(j['jugador'])} {verbo} {decir(e['umbral'])} {etiqueta if k == 0 else ''}".strip()
              + (" o más," if k == 0 else ","), cue=f"medidor{k}") \
            .t(f"{eq[lado]['ciudad']} gana el").p(e["p_gana"], cue=f"sube{k}", fin=".")
        medidores.append({"athlete_id": j["athlete_id"], "jugador": _apellido(j["jugador"]),
                          "evento": e["texto"].upper(), "color": eq[lado]["color"],
                          "equipo": f"{eq[lado]['apodo']} GANAN", "base": pct(p_gana[lado]), "pct": pct(e["p_gana"])})
    escenas.append({"tipo": "decide", "props": {"titulo": "¿QUÉ LO DECIDE?", "medidores": medidores},
                    "narracion": nar.trozos})

    # 10. Cierre.
    nar = Narracion().t(f"¿{eq['away']['apodo']} o {eq['home']['apodo']}?").t("¿Con quién vas?", cue="pregunta") \
        .t("Déjalo en los comentarios.", cue="comenta").t("Mañana revisamos.")
    escenas.append({"tipo": "cierre", "props": {"titulo": "¿CON QUIÉN VAS?", "linea1": "COMENTA TU PICK",
                                              "linea2": "RESULTADO MAÑANA"}, "narracion": nar.trozos})

    return {
        "game_id": d["game_id"], "liga": "nba", "marca": MARCA, "simulaciones": n, "fecha": _fecha(d["starts_at"]),
        "equipos": eq, "cinta": d["cinta"], "escenas": escenas,
    }


# ---- Formato corto ------------------------------------------------------------

# Con que numero "destaca" un jugador en cada estadistica: sirve para escoger
# cual de sus tres numeros se resalta.
_DESTACA = {"points": 22.0, "reb": 11.0, "assists": 9.0}
_ROTULO = {"points": "PUNTOS", "reb": "REBOTES", "assists": "ASISTENCIAS"}
_CORTO = {"points": "PTS", "reb": "REB", "assists": "AST"}
_VERBO = {"points": "mete", "reb": "baja", "assists": "reparte"}


def _figura(jugadores: list[dict]) -> dict:
    """El que mas produce del equipo, contando puntos, rebotes y asistencias."""
    return max(jugadores, key=lambda j: j["media"]["points"] + 1.2 * j["media"]["reb"] + 1.5 * j["media"]["assists"])


def _extra(j: dict, mejor: str) -> tuple[str, float, int | None]:
    """Un dato mas de la figura: doble-doble si es comun; si no, que tan seguido
    pasa de un numero alto en lo que mejor hace."""
    if j["doble_doble"] >= 0.30:
        return "DOBLE-DOBLE", j["doble_doble"], None
    u = min(j["sobre"][mejor], key=lambda u: abs(j["sobre"][mejor][u] - 0.33))
    return f"{u}+ {_ROTULO[mejor]}", j["sobre"][mejor][u], int(u)


def _lejos(a: str, b: str, umbral: float = 130) -> bool:
    """Dos colores hex se distinguen en pantalla si estan lejos en RGB."""
    c = [int(x[i:i + 2], 16) for x in (a, b) for i in (1, 3, 5)]
    return sum((c[k] - c[k + 3]) ** 2 for k in range(3)) ** 0.5 >= umbral


def _contrastar(eq: dict) -> None:
    """Si los dos equipos se parecen (dos rojos, dos azules), el visitante toma su
    segundo color o, si tampoco contrasta, blanco. Los cuadros de la simulacion
    tienen que leerse de los dos lados."""
    if _lejos(eq["home"]["color"], eq["away"]["color"]):
        return
    if _lejos(eq["home"]["color"], eq["away"]["color2"]):
        eq["away"]["color"] = eq["away"]["color2"]
    else:
        eq["away"]["color"] = "#e3ebef"


def _peso(e: dict) -> float:
    """Que tanto empuja un evento, con un pequeno bonus a rebotes y asistencias
    para que no todas las llaves sean de puntos."""
    return e["empuje"] * e["p_evento"] ** 0.5 * (1.0 if e["stat"] == "points" else 1.6)


def construir_corto(d: dict, metricas: dict | None = None) -> dict:
    """Version corta de NBA: siete bloques, sin dar pick.

    Gancho, como se hizo, quien gana mas veces, la figura de cada equipo con
    sus tres numeros (resaltado el mejor), la llave de cada lado y el cierre.
    """
    n = d["simulaciones"]
    eq = {lado: equipo(d["equipos"][lado]["abbr"]) for lado in ("home", "away")}
    _contrastar(eq)
    jug = d["jugadores"]
    favorito = "home" if d["victorias"]["home"] >= d["victorias"]["away"] else "away"
    otro = "away" if favorito == "home" else "home"
    p_gana = {lado: d["victorias"][lado] / n for lado in ("home", "away")}
    fav, riv = eq[favorito], eq[otro]
    # El dato principal del gancho sale de la figura del favorito: cambia de un video a otro.
    fig_fav = _figura(jug[favorito])
    principal = max(_DESTACA, key=lambda s: fig_fav["media"][s] / _DESTACA[s])
    ap = _apellido(fig_fav["jugador"])
    frase, rotulo = {
        "points": (f"Todo pasa por {ap}.", f"TODO PASA POR {ap.upper()}"),
        "reb": (f"Todo pasa por los rebotes de {ap}.", f"LOS REBOTES DE {ap.upper()}"),
        "assists": (f"Todo pasa por las asistencias de {ap}.", f"LAS ASISTENCIAS DE {ap.upper()}"),
    }[principal]
    if len(rotulo) > 26:  # un nombre largo no cabe en el letrero: se usa el equipo
        frase, rotulo = f"Todo pasa por el {fav['apodo']}.", f"TODO PASA POR {fav['apodo'].upper()}"

    record = None
    if metricas:
        mls = [v["markets"]["moneyline"] for v in metricas["versions"] if v.get("markets", {}).get("moneyline")]
        total = sum(ml["n"] for ml in mls)
        if total:
            aciertos = int(round(sum(ml["n"] * ml["hit_rate"] for ml in mls)))
            record = {"aciertos": aciertos, "fallos": total - aciertos}
    escenas = []

    # 1. Gancho: la pregunta, sin dar pick.
    nar = Narracion().t(f"¿{eq['away']['apodo']} o {eq['home']['apodo']}?", cue="pick").t(frase, cue="remate")
    escenas.append({"tipo": "gancho", "props": {
        "linea1": f"¿{eq['away']['apodo']} O {eq['home']['apodo']}?".upper(), "linea2": rotulo, "favorito": None},
        "narracion": nar.trozos})

    # 2. Como se hizo.
    nar = Narracion().t("Tomamos cómo viene jugando cada equipo", cue="paso0").t("y cada jugador,", cue="paso1")         .t("y lo simulamos").n(n, cue="cuenta").t("veces.")
    escenas.append({"tipo": "explica", "props": {
        "titulo": "Cómo lo hicimos", "pasos": ["CÓMO VIENE CADA EQUIPO", "CÓMO VIENE CADA JUGADOR"]},
        "narracion": nar.trozos})

    # 3. Quien gana mas veces y el marcador.
    mm = d["marcador_medio"]
    alto, bajo = sorted((round(mm["home"]), round(mm["away"])), reverse=True)
    nar = Narracion().t(f"Los {fav['apodo']} ganaron el", cue="cuenta").p(p_gana[favorito], fin=".")         .t("Marcador promedio:", cue="veredicto").n(alto).t("a").n(bajo, sufijo=".")
    escenas.append({"tipo": "resultado", "props": {
        "titulo": "¿Quién gana?", "victorias": d["victorias"], "muestra": d["muestra"],
        "veredicto": f"MARCADOR PROMEDIO: {round(mm['away'])}-{round(mm['home'])}",
        "marcador": {"home": round(mm["home"]), "away": round(mm["away"])}, "favorito": favorito},
        "narracion": nar.trozos})

    # 4 y 5. La figura de cada equipo: sus tres numeros, resaltado el mejor.
    for lado in (favorito, otro):
        j = _figura(jug[lado])
        mejor = max(_DESTACA, key=lambda s: j["media"][s] / _DESTACA[s])
        rotulo, p, umbral = _extra(j, mejor)
        # Son las estadisticas de ESTE partido, no el promedio de la temporada.
        nar = Narracion().t(f"Por los {eq[lado]['apodo']}, {j['jugador']}.", cue="figura") \
            .t("En este partido:").n(round(j["media"][mejor]), cue="mejor").t(f"{_ROTULO[mejor].lower()},")
        if umbral is None:
            nar.t("y firma doble-doble en el", cue="extra").p(p, fin=".")
        else:
            nar.t(f"y llega a {umbral} en el", f"y llega a {decir(umbral)} en el", cue="extra").p(p, fin=".")
        escenas.append({"tipo": "figura", "props": {
            "titulo": "La figura" if lado == favorito else "Y del otro lado",
            "athlete_id": j["athlete_id"], "jugador": j["jugador"], "color": eq[lado]["color"],
            "abbr": eq[lado]["abbr"], "equipo": eq[lado]["apodo"],
            "stats": [{"valor": int(round(j["media"][s])), "etiqueta": _ROTULO[s], "corto": _CORTO[s],
                       "mejor": s == mejor} for s in ("points", "reb", "assists")],
            "extra": {"valor": f"{pct(p)}%", "etiqueta": f"DE LAS SIMS CON {rotulo}"}},
            "narracion": nar.trozos})

    # 6. La llave de cada lado: el evento que mas empuja a cada equipo.
    nar = Narracion().t("¿Qué lo decide?")
    medidores = []
    for k, lado in enumerate((favorito, otro)):
        ops = [(j, e) for j in jug[lado] for e in j["eventos"] if e["p_evento"] >= 0.15 and e["empuje"] > 0]
        if not ops:
            continue
        j, e = max(ops, key=lambda x: _peso(x[1]))
        frase = f"{'Si' if k == 0 else 'Pero si'} {_apellido(j['jugador'])} {_VERBO[e['stat']]} {{}} {_ROTULO[e['stat']].lower()},"
        nar.t(frase.format(e["umbral"]), frase.format(decir(e["umbral"])), cue=f"medidor{k}")             .t(f"los {eq[lado]['apodo']} ganan el").p(e["p_gana"], cue=f"sube{k}", fin=".")
        medidores.append({"athlete_id": j["athlete_id"], "jugador": _apellido(j["jugador"]),
                          "evento": e["texto"].upper(), "color": eq[lado]["color"],
                          "equipo": f"{eq[lado]['apodo']} GANAN", "base": pct(p_gana[lado]), "pct": pct(e["p_gana"])})
    if medidores:
        escenas.append({"tipo": "decide", "props": {"titulo": "La llave de cada lado", "medidores": medidores},
                        "narracion": nar.trozos})

    # 7. Cierre: sin pick; la pregunta y el comentario.
    nar = Narracion().t("¿Tú a quién le vas?", cue="pregunta")         .t("Comenta: predicción,", cue="comenta").t("si quieres ver toda la predicción.")
    escenas.append({"tipo": "cierre", "props": {
        "titulo": "¿A quién\nle vas?", "palabra": "PREDICCIÓN", "linea1": "Comenta “predicción”",
        "linea2": "Y VE TODA LA PREDICCIÓN"}, "narracion": nar.trozos})

    return {"game_id": d["game_id"], "liga": "nba", "marca": MARCA, "simulaciones": n, "record": record,
            "fecha": _fecha(d["starts_at"]), "equipos": eq, "cinta": d["cinta"], "escenas": escenas}


if __name__ == "__main__":
    datos = json.load(open(sys.argv[1]))
    met = json.load(open(sys.argv[2])) if len(sys.argv) > 3 and sys.argv[2] != "-" else None
    g = construir(datos, met)
    json.dump(g, open(sys.argv[-1], "w"), ensure_ascii=False, indent=1)
    for e in g["escenas"]:
        print(f"[{e['tipo']}]", " ".join(t["texto"] for t in e["narracion"]))
    print(sum(len(t["voz"].split()) for e in g["escenas"] for t in e["narracion"]), "palabras")
