"""Datos por partido para el video corto (TikTok): lo que un resumen no guarda.

Edgebook lee medias y escaleras; el video cuenta historias que solo salen de
las simulaciones una por una: el mejor partido de un jugador en 20,000, cuantas
veces gana su equipo cuando el pasa de 30, que tan cerrado sale el marcador.
Todo se calcula con las mismas simulaciones que publican los mercados y los
props, asi que los numeros del video cuadran con los de Edgebook.

Se escribe un archivo por partido en `data/video/<game_id>.json`.
"""

from __future__ import annotations

import numpy as np

# Umbrales que se prueban por estadistica para "cuando X hace N o mas".
UMBRALES = {
    "points": (15, 20, 25, 30, 35, 40),
    "reb": (8, 10, 12, 15),
    "assists": (6, 8, 10, 12),
}
ETIQUETA = {"points": "puntos", "reb": "rebotes", "assists": "asistencias"}
# Un evento sirve para contar si pasa seguido pero no siempre.
P_EVENTO = (0.12, 0.60)
CINTA = 120  # resultados sim por sim que se guardan para la cinta
MUESTRA = 1000  # ganadores de las primeras sims, para la cuadricula


def _jugador(a: int, nombre: str, x: dict, gana: np.ndarray) -> dict:
    """Resumen de un jugador y como se mueve la victoria de su equipo con el."""
    pts, reb, ast = x["points"], x["reb"], x["assists"]
    base = float(gana.mean())
    dobles = (pts >= 10).astype(int) + (reb >= 10).astype(int) + (ast >= 10).astype(int)
    mejor = int(np.argmax(pts))
    eventos = []
    for s, umbrales in UMBRALES.items():
        for u in umbrales:
            pasa = x[s] >= u
            p = float(pasa.mean())
            if not P_EVENTO[0] <= p <= P_EVENTO[1]:
                continue
            eventos.append({
                "stat": s, "umbral": u, "texto": f"{u}+ {ETIQUETA[s]}",
                "p_evento": round(p, 4),
                "p_gana": round(float(gana[pasa].mean()), 4),
                "p_gana_si_no": round(float(gana[~pasa].mean()), 4),
                "empuje": round(float(gana[pasa].mean()) - base, 4),
            })
    return {
        "athlete_id": int(a),
        "jugador": nombre,
        "minutos": round(float(x["info"]["minutos"]), 1),
        "media": {s: round(float(x[s].mean()), 1) for s in UMBRALES},
        "sobre": {
            s: {str(u): round(float((x[s] >= u).mean()), 4) for u in umbrales}
            for s, umbrales in UMBRALES.items()
        },
        "doble_doble": round(float((dobles >= 2).mean()), 4),
        "triple_doble": round(float((dobles >= 3).mean()), 4),
        # Su partido mas anotador en todas las simulaciones, con lo demas de
        # esa misma simulacion.
        "mejor": {
            "points": int(pts[mejor]), "reb": int(reb[mejor]), "assists": int(ast[mejor]),
            "gano": bool(gana[mejor]),
        },
        "eventos": sorted(eventos, key=lambda e: -abs(e["empuje"])),
    }


def construir(g: dict, sim, sims_props: dict, rotacion: dict, nombres: dict) -> dict:
    """`sim` es la `Simulacion` del partido; `sims_props`, la salida de
    `props.simular_props`; `rotacion`, lado -> {athlete_id: minutos}."""
    margen = np.asarray(sim.casa - sim.visita)
    n = len(margen)
    gana_casa = margen > 0
    ot = np.asarray(sim.casa_reg == sim.visita_reg)
    lados = {"home": gana_casa, "away": ~gana_casa}
    # Histograma del margen de casa, de 3 en 3; las colas se juntan en la orilla.
    orillas = np.arange(-31.5, 32.5, 3.0)
    cuentas, _ = np.histogram(np.clip(margen, -31, 31), bins=orillas)
    abbr = {"home": g["home_abbr"], "away": g["away_abbr"]}
    jugadores = {
        lado: [
            _jugador(a, nombres[a], sims_props[a], lados[lado])
            for a in sorted(rotacion[lado], key=lambda a: -rotacion[lado][a])
            if a in sims_props
        ]
        for lado in ("home", "away")
    }
    return {
        "game_id": g["game_id"],
        "starts_at": g["starts_at"],
        "simulaciones": n,
        "equipos": {
            lado: {"abbr": abbr[lado], "team_id": g[f"{lado}_id"], "nombre": g.get(f"{lado}_nombre")}
            for lado in ("home", "away")
        },
        "victorias": {"home": int(gana_casa.sum()), "away": int(n - gana_casa.sum())},
        "marcador_medio": {"home": round(float(sim.casa.mean()), 1), "away": round(float(sim.visita.mean()), 1)},
        "margen": {
            "desde": float(orillas[0]), "ancho": 3.0, "cuentas": cuentas.tolist(),
            "cerrados_5": round(float((np.abs(margen) <= 5).mean()), 4),
            "palizas_20": round(float((np.abs(margen) >= 20).mean()), 4),
            "tiempo_extra": round(float(ot.mean()), 4),
        },
        # Ganador y margen de las primeras simulaciones, en el orden en que salieron.
        "cinta": [
            {"gana": abbr["home" if m > 0 else "away"], "por": int(abs(m))}
            for m in margen[:CINTA]
        ],
        "muestra": "".join("h" if x else "a" for x in gana_casa[:MUESTRA]),
        "jugadores": jugadores,
    }
