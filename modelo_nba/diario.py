"""Corrida del dia: ajusta, proyecta el slate, simula y publica.

Corre varias veces al dia. Cada corrida publica lo mas fresco y deja constancia
de todo lo que proyecto. La prediccion que se califica es la OFICIAL: la ultima
generada con al menos 60 minutos de anticipacion al inicio del partido. Asi la
regla no depende de a que hora corrio el cron ni de quien apreto un boton, y
usa el reporte de bajas mas reciente que se tenia a esa hora.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from . import VERSION, datos, emitir, espn, historico, props
from . import minutos as mn
from .mercados import mercados
from .motores import elo, equipos, factores
from .parametros import cargar_arbitro, cargar_parametros
from .proyeccion import esperar
from .ratings import ajustar
from .simulador import simular

ET = "America/New_York"
ANTICIPACION_OFICIAL = dt.timedelta(minutes=60)
DATA = Path("data")
# Sin historial y sin draft (two-way, contrato de 10 dias): casi no juegan.
MINUTOS_SIN_NADA = 2.0


def temporada_de(fecha: dt.date) -> int:
    """ESPN nombra la temporada por el ano en que termina."""
    return fecha.year + 1 if fecha.month >= 8 else fecha.year


def _b2b(calendario: pd.DataFrame, team_id: int, fecha: dt.date) -> bool:
    ayer = fecha - dt.timedelta(days=1)
    c = calendario[calendario.dia == ayer]
    return bool(((c.home_id.astype(int) == team_id) | (c.away_id.astype(int) == team_id)).any())


def _rotacion(roster, base, novatos_pick, nombres):
    """Base de minutos esperada (ya ponderada por probabilidad de jugar).

    Devuelve tambien los minutos habituales que se esperan perdidos por bajas,
    que es una de las dos cosas que mira el arbitro.
    """
    esperada, completa, avisos, fuera = {}, {}, [], []
    perdidos = 0.0
    for r in roster:
        a = r["athlete_id"]
        b = base.get(a)
        if b is None or b != b:
            pick = novatos_pick.get(datos.clave_nombre(r["nombre"]))
            b = datos.minutos_novato(pick) if pick is not None else MINUTOS_SIN_NADA
        nombres[a] = r["nombre"]
        completa[a] = b
        perdidos += b * (1 - r["prob_juega"])
        if r["prob_juega"] <= 0:
            if b >= 10:
                fuera.append(r["nombre"])
            continue
        esperada[a] = b * r["prob_juega"]
        if r["prob_juega"] < 1 and b >= 15:
            avisos.append(f"{r['nombre']} está en duda ({r['estado']})")
        if not r["estado_conocido"]:
            avisos.append(f"Estado desconocido para {r['nombre']}: '{r['estado']}'")
    return esperada, completa, avisos, fuera, perdidos


def predecir(
    fecha: dt.date | None = None,
    ahora: pd.Timestamp | None = None,
    salida: Path = DATA,
    registrar_oficial: bool = True,
) -> dict:
    """Proyecta el slate y publica.

    `registrar_oficial=False` publica sin tocar la prediccion oficial: es lo
    que usa el boton de Edgebook. Si un boton pudiera escribirla, la hora en que
    alguien lo apreto decidiria que prediccion se califica.
    """
    ahora = ahora or pd.Timestamp.now(tz="UTC")
    fecha = fecha or ahora.tz_convert(ET).date()
    temporada = temporada_de(fecha)
    params_r, params_s = cargar_parametros()

    cal = datos.calendario(temporada)
    regulares = cal[cal.season_type == 2]
    inicio = regulares.dia.min() if len(regulares) else None
    p, j = datos.historia(temporada, fecha, inicio)
    # Todo se ajusta al inicio del dia (hora del Este), no a la hora de la
    # corrida: los datos son los mismos todo el dia (hasta ayer) y asi las
    # corridas del mismo dia solo cambian por las bajas, no por decimales del
    # decaimiento temporal.
    corte = min(ahora, pd.Timestamp(fecha).tz_localize(ET).tz_convert("UTC"))
    R = ajustar(p, j, corte, params_r)
    bases = {
        False: mn.minutos_actuales(j, p, corte).to_dict(),
        True: mn.minutos_actuales(j, p, corte, playoffs=True).to_dict(),
    }
    # Los otros tres motores y el arbitro.
    estado_elo = elo.historial(p)[1]
    R_equipos = equipos.ajustar(p, corte)
    tabla_f = factores.tabla_equipos(p, j)
    mapeo_f = factores.ajustar_mapeo(tabla_f)
    equipos_f, liga_f = factores.estado_actual(tabla_f)
    arbitro = cargar_arbitro()
    actual = p[p.season == temporada]
    jugados = pd.concat([actual.home_id, actual.away_id]).value_counts().to_dict()
    # Props: tasas por posesion, lo que permite cada defensa y los promedios
    # recientes, todo con lo jugado antes del dia.
    try:
        tabla_props = props.tabla_jugador_partido(j, p)
        tasas_props = props.tasas(tabla_props, corte)
        prom_props = props.promedios(tabla_props, corte, temporada)
    except Exception:  # noqa: BLE001 -- sin props, el resto se publica igual
        tasas_props = prom_props = None
    draft = datos.novatos(temporada)
    picks = dict(zip(draft.clave, draft.overall_pick.astype(int)))

    slate = [
        g for g in espn.scoreboard(fecha)
        if g["season_type"] in historico.TIPOS_VALIDOS
        and historico.es_franquicia(g["home_id"]) and historico.es_franquicia(g["away_id"])
    ]
    generado = ahora.isoformat().replace("+00:00", "Z")
    avisos_globales = []
    if not slate:
        avisos_globales.append("Sin partidos de temporada en el slate")

    rosters: dict[int, list] = {}
    salida_juegos, detalle, registro = [], [], []
    for g in slate:
        if g["estado"] != "pre":
            continue
        nombres: dict[int, str] = {}
        rot, rot_completa, rot_props, avisos, bajas, perdidos = {}, {}, {}, [], {}, {}
        ausente: dict[str, str | None] = {}
        for lado in ("home", "away"):
            tid = g[f"{lado}_id"]
            if tid not in rosters:
                rosters[tid] = espn.roster(tid)
            base = bases[g["season_type"] == 3]
            esperada, completa, av, fuera, perdidos[lado] = _rotacion(rosters[tid], base, picks, nombres)
            rot[lado] = mn.repartir(esperada)
            rot_completa[lado] = mn.repartir(completa)
            # Para props, los minutos si juega: un prop se anula si no juega,
            # asi que el que esta en duda se proyecta con su rol completo.
            rot_props[lado] = mn.repartir({a: completa[a] for a in esperada})
            avisos += av
            bajas[lado] = fuera
            # El ausente que mas minutos se lleva, para explicar los props.
            fuera_ids = [r["athlete_id"] for r in rosters[tid] if r["prob_juega"] <= 0]
            top = max(fuera_ids, key=lambda a: completa.get(a, 0.0), default=None)
            ausente[lado] = (nombres[top].split()[-1] if top is not None and completa.get(top, 0) >= 20
                             else None)
        b2b = {lado: _b2b(cal, g[f"{lado}_id"], fecha) for lado in ("home", "away")}
        args = (R, temporada, g["home_id"], g["away_id"])
        e = esperar(*args, rot["home"], rot["away"], g["neutral"], b2b["home"], b2b["away"])
        e_full = esperar(*args, rot_completa["home"], rot_completa["away"], g["neutral"], b2b["home"], b2b["away"])
        perdida = {
            # Lo que pierde cada equipo en margen por sus ausencias.
            "home": max(0.0, (e_full.puntos_casa - e_full.puntos_visita) - (e.puntos_casa - e.puntos_visita)),
            "away": max(0.0, (e.puntos_casa - e.puntos_visita) - (e_full.puntos_casa - e_full.puntos_visita)),
        }
        casa, visita, temp, neutral = g["home_id"], g["away_id"], temporada, g["neutral"]
        f_pred = factores.predecir(equipos_f, liga_f, mapeo_f, casa, visita, neutral)
        eq_c, eq_v = R_equipos.predecir(casa, visita, temp, neutral)
        margenes = {
            "jugadores": e.puntos_casa - e.puntos_visita,
            "elo": elo.predecir(estado_elo, casa, visita, temp, neutral),
            "equipos": eq_c - eq_v,
            "factores": f_pred[0] - f_pred[1] if f_pred else float("nan"),
        }
        total_j = e.puntos_casa + e.puntos_visita
        decision = arbitro.combinar(
            margenes, {"jugadores": total_j},
            min(jugados.get(casa, 0), jugados.get(visita, 0)),
            max(perdidos.values()) / 240,
        )
        pts_casa = (decision["total"] + decision["margen"]) / 2
        pts_visita = (decision["total"] - decision["margen"]) / 2
        sim = simular(pts_casa, pts_visita, params_s, semilla=g["game_id"])
        m = mercados(sim)
        # Los props son un extra: si fallan, el partido se publica sin ellos.
        try:
            sims_props = props.simular_props(
                tasas_props, rot_props, {"home": casa, "away": visita},
                {"home": sim.casa, "away": sim.visita}, sim.casa - sim.visita, e.pace,
                semilla=g["game_id"] + 1, prom=prom_props, minutos_completos=rot_completa,
            )
            en_duda = {r["athlete_id"] for tid in (casa, visita) for r in rosters[tid] if 0 < r["prob_juega"] < 1}
            rival_abbr = {"home": g["away_abbr"], "away": g["home_abbr"]}

            def _prop(a, lado):
                x = sims_props[a]
                res = props.resumir(x)
                medias = {s: float(x[s].mean()) for s in props.STATS}
                clave = props.insight(x["info"], medias, rival_abbr[lado], ausente[lado], a in en_duda)
                return dict(jugador=nombres[a], athlete_id=a, en_duda=a in en_duda,
                            insight=clave, **res)

            props_juego = {
                lado: [
                    _prop(a, lado)
                    for a in sorted(rot_props[lado], key=lambda a: -rot_props[lado][a])
                    if a in sims_props
                ]
                for lado in ("home", "away")
            }
        except Exception as err:  # noqa: BLE001
            props_juego = {"error": f"{type(err).__name__}: {err}"}
        proy = emitir.proyeccion(
            g, m, e, {k: (perdida[k], bajas[k]) for k in perdida}, avisos, margenes
        )
        salida_juegos.append(proy)
        inicio_juego = pd.Timestamp(g["starts_at"])
        detalle.append({
            "game_id": g["game_id"],
            "starts_at": g["starts_at"],
            "home": g["home_abbr"],
            "away": g["away_abbr"],
            "esperado": {
                "puntos_casa": round(e.puntos_casa, 2),
                "puntos_visita": round(e.puntos_visita, 2),
                "pace": round(e.pace, 2),
                "desglose": {k: round(v, 2) for k, v in e.desglose.items()},
            },
            "rotacion": {
                lado: sorted(
                    ({"jugador": nombres[a], "minutos": round(mm, 1)} for a, mm in rot[lado].items() if mm >= 1),
                    key=lambda x: -x["minutos"],
                )
                for lado in ("home", "away")
            },
            "b2b": b2b,
            "modelos": {
                "margen_casa": {k: round(v, 2) for k, v in margenes.items() if v == v},
                "arbitro": {
                    "grupo": decision["grupo"],
                    "pesos": {k: round(v, 3) for k, v in decision["pesos_margen"].items()},
                    "margen_casa": round(decision["margen"], 2),
                },
            },
            "mercados": m,
            "props": props_juego,
        })
        registro.append({
            "generated_at": generado,
            "model_version": VERSION,
            "game_id": g["game_id"],
            "starts_at": g["starts_at"],
            "minutos_antes": round((inicio_juego - ahora).total_seconds() / 60, 1),
            "proyeccion": proy,
            "mercados": m,
        })

    fecha_s = fecha.isoformat()
    if registrar_oficial:
        oficiales = registrar(salida, fecha_s, registro, ahora)
    else:
        ruta = salida / "oficiales" / f"{fecha_s}.json"
        oficiales = json.loads(ruta.read_text()) if ruta.exists() else {}
    # Los partidos que ya empezaron siguen en el snapshot con su prediccion
    # oficial congelada, para que no desaparezcan de Edgebook al arrancar.
    vivos = {x["league_game_id"] for x in salida_juegos}
    for gid, o in oficiales.items():
        if gid not in vivos:
            salida_juegos.append(o["proyeccion"])

    emitir.escribir_si_cambia(salida / "edgebook-latest.json",
                    emitir.envelope(fecha_s, generado, VERSION, salida_juegos, avisos_globales))
    emitir.escribir_si_cambia(salida / "latest.json", {
        "model_version": VERSION, "generated_at": generado, "date_local": fecha_s,
        "ratings": {"mu": R.mu_actual(temporada), "localia": R.localia,
                    "contexto": R.contexto, "pace": R.pace_actual(temporada)},
        "games": detalle,
    })
    return {"juegos": len(salida_juegos), "proyectados": len(detalle), "oficiales": len(oficiales)}


def registrar(salida: Path, fecha: str, registro: list[dict], ahora: pd.Timestamp) -> dict:
    """Actualiza la prediccion oficial de cada partido con esta corrida.

    Oficial = la ultima con `minutos_antes >= 60`. Una vez que un partido entra
    a su ultima hora ninguna corrida posterior califica, asi que queda fija.
    Si el cron fallo y ninguna corrida llego con 60 minutos, se guarda la
    primera que hubo y se marca `tardia`: es preferible calificar una
    prediccion tardia, dicha como tal, que no calificar nada.

    Solo se guarda la candidata, no cada corrida: con ~24 corridas al dia la
    bitacora completa pesaria cientos de MB por temporada en git.
    """
    ruta = salida / "oficiales" / f"{fecha}.json"
    oficiales = json.loads(ruta.read_text()) if ruta.exists() else {}
    limite = ANTICIPACION_OFICIAL.total_seconds() / 60
    for r in registro:
        gid = str(r["game_id"])
        if r["minutos_antes"] >= limite:
            oficiales[gid] = dict(r, tardia=False)
        elif gid not in oficiales:
            oficiales[gid] = dict(r, tardia=True)
    emitir.escribir_si_cambia(ruta, oficiales)
    return oficiales
