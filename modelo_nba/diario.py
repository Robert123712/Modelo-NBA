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

from . import VERSION, datos, emitir, espn, historico
from . import minutos as mn
from .mercados import mercados
from .parametros import cargar_parametros
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
    """Base de minutos esperada (ya ponderada por probabilidad de jugar)."""
    esperada, completa, avisos, fuera = {}, {}, [], []
    for r in roster:
        a = r["athlete_id"]
        b = base.get(a)
        if b is None or b != b:
            pick = novatos_pick.get(datos.clave_nombre(r["nombre"]))
            b = datos.minutos_novato(pick) if pick is not None else MINUTOS_SIN_NADA
        nombres[a] = r["nombre"]
        completa[a] = b
        if r["prob_juega"] <= 0:
            if b >= 10:
                fuera.append(r["nombre"])
            continue
        esperada[a] = b * r["prob_juega"]
        if r["prob_juega"] < 1 and b >= 15:
            avisos.append(f"{r['nombre']} está en duda ({r['estado']})")
        if not r["estado_conocido"]:
            avisos.append(f"Estado desconocido para {r['nombre']}: '{r['estado']}'")
    return esperada, completa, avisos, fuera


def predecir(fecha: dt.date | None = None, ahora: pd.Timestamp | None = None, salida: Path = DATA) -> dict:
    ahora = ahora or pd.Timestamp.now(tz="UTC")
    fecha = fecha or ahora.tz_convert(ET).date()
    temporada = temporada_de(fecha)
    params_r, params_s = cargar_parametros()

    cal = datos.calendario(temporada)
    regulares = cal[cal.season_type == 2]
    inicio = regulares.dia.min() if len(regulares) else None
    p, j = datos.historia(temporada, fecha, inicio)
    R = ajustar(p, j, ahora, params_r)
    bases = {
        False: mn.minutos_actuales(j, p, ahora).to_dict(),
        True: mn.minutos_actuales(j, p, ahora, playoffs=True).to_dict(),
    }
    draft = datos.novatos(temporada)
    picks = dict(zip(draft.clave, draft.overall_pick.astype(int)))

    slate = [g for g in espn.scoreboard(fecha) if g["season_type"] in historico.TIPOS_VALIDOS]
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
        rot, rot_completa, avisos, bajas = {}, {}, [], {}
        for lado in ("home", "away"):
            tid = g[f"{lado}_id"]
            if tid not in rosters:
                rosters[tid] = espn.roster(tid)
            base = bases[g["season_type"] == 3]
            esperada, completa, av, fuera = _rotacion(rosters[tid], base, picks, nombres)
            rot[lado] = mn.repartir(esperada)
            rot_completa[lado] = mn.repartir(completa)
            avisos += av
            bajas[lado] = fuera
        b2b = {lado: _b2b(cal, g[f"{lado}_id"], fecha) for lado in ("home", "away")}
        args = (R, temporada, g["home_id"], g["away_id"])
        e = esperar(*args, rot["home"], rot["away"], g["neutral"], b2b["home"], b2b["away"])
        e_full = esperar(*args, rot_completa["home"], rot_completa["away"], g["neutral"], b2b["home"], b2b["away"])
        perdida = {
            # Lo que pierde cada equipo en margen por sus ausencias.
            "home": max(0.0, (e_full.puntos_casa - e_full.puntos_visita) - (e.puntos_casa - e.puntos_visita)),
            "away": max(0.0, (e.puntos_casa - e.puntos_visita) - (e_full.puntos_casa - e_full.puntos_visita)),
        }
        sim = simular(e.puntos_casa, e.puntos_visita, params_s, semilla=g["game_id"])
        m = mercados(sim)
        proy = emitir.proyeccion(
            g, m, e, {k: (perdida[k], bajas[k]) for k in perdida}, avisos
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
            "mercados": m,
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
    oficiales = registrar(salida, fecha_s, registro, ahora)
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
