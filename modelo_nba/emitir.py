"""Lo que se publica: el contrato de Edgebook y el detalle por mercado.

`edgebook-latest.json` sigue el envelope que Edgebook ya lee para MLB y NFL
(lib/models/contract.ts). `latest.json` lleva las escaleras completas de cada
mercado, para la pagina propia del modelo.
"""

from __future__ import annotations

import json
from pathlib import Path

from .proyeccion import Esperado

SCHEMA_VERSION = "1.1"


def _redondear_medio(x: float) -> float:
    return round(x * 2) / 2


def _equipo(j: dict, lado: str) -> dict:
    return {"name": j[f"{lado}_nombre"], "code": j[f"{lado}_abbr"]}


def factores(
    juego: dict,
    e: Esperado,
    bajas: dict[str, tuple[float, list[str]]],
    lado_pick: str,
) -> list[dict]:
    """Por que el modelo ve el partido asi, en puntos de margen.

    `bajas[lado]` = (puntos que pierde ese equipo por sus ausencias, nombres).
    """
    casa, visita = juego["home_abbr"], juego["away_abbr"]
    d = e.desglose
    out = []

    plantilla = d["ofensiva_casa"] + d["defensa_casa"] + d["ofensiva_visita"] + d["defensa_visita"]
    if abs(plantilla) >= 0.5:
        favor = "home" if plantilla > 0 else "away"
        out.append({
            "label": "Rotación",
            "favors": favor,
            "detail": (
                f"Con los minutos proyectados, la rotación de {casa if favor == 'home' else visita} "
                f"vale {abs(plantilla):.1f} puntos más por partido."
            ),
        })
    if d["localia"] > 0:
        out.append({
            "label": "Localía",
            "favors": "home",
            "detail": f"Jugar en casa vale {d['localia']:.1f} puntos para {casa}.",
        })
    if abs(d["descanso"]) >= 0.3:
        favor = "home" if d["descanso"] > 0 else "away"
        cansado = visita if favor == "home" else casa
        out.append({
            "label": "Descanso",
            "favors": favor,
            "detail": f"{cansado} juega su segundo partido en dos noches: {abs(d['descanso']):.1f} puntos.",
        })
    for lado, abbr, rival in (("home", casa, "away"), ("away", visita, "home")):
        puntos, nombres = bajas.get(lado, (0.0, []))
        if puntos >= 0.5 and nombres:
            out.append({
                "label": f"Bajas de {abbr}",
                "favors": rival,
                "detail": f"Sin {', '.join(nombres[:3])}: {abbr} pierde {puntos:.1f} puntos.",
            })
    for f in out:
        f["supports_pick"] = f["favors"] == lado_pick
        f["label"] = f["label"][:40]
        f["detail"] = f["detail"][:300]
    out.sort(key=lambda f: not f["supports_pick"])
    return out[:5]


def proyeccion(
    juego: dict,
    m: dict,
    e: Esperado,
    bajas: dict,
    avisos: list[str],
) -> dict:
    """Una entrada de `games` del envelope de Edgebook."""
    p_casa = m["ganador"]["casa"]
    lado = "home" if p_casa >= 0.5 else "away"
    equipo = juego[f"{lado}_nombre"]
    margen = m["margen"]["mediana"]
    return {
        "league_game_id": str(juego["game_id"]),
        "espn_game_id": str(juego["game_id"]),
        "starts_at": juego["starts_at"],
        "home": _equipo(juego, "home"),
        "away": _equipo(juego, "away"),
        "projection": {
            "home_score": round(m["puntos_casa"]["media"], 1),
            "away_score": round(m["puntos_visita"]["media"], 1),
        },
        "win_probability": {
            "home": round(p_casa, 4),
            "away": round(1 - p_casa, 4),
        },
        "pick": {"market": "moneyline", "side": lado, "label": f"{equipo} ML"[:80]},
        "data_warning": avisos[0][:200] if avisos else None,
        "spread": {"home": _redondear_medio(-margen), "away": _redondear_medio(margen)},
        "total_points": round(m["total"]["media"], 1),
        "season": juego["season"],
        "intervals_80": {
            "home_margin": [m["margen"]["p10"], m["margen"]["p90"]],
            "total": [m["total"]["p10"], m["total"]["p90"]],
        },
        "game_warnings": [a[:300] for a in avisos[:12]],
        "warnings": [],
        "key_factors": factores(juego, e, bajas, lado),
    }


def envelope(fecha: str, generado: str, version: str, juegos: list[dict], avisos: list[str]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "sport": "NBA",
        "model_version": version,
        "generated_at": generado,
        "date_local": fecha,
        "games": juegos[:40],
        "skipped_without_id": 0,
        "warnings": avisos[:10],
    }


def escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1))
    tmp.replace(ruta)


def _sin_sello(x):
    if isinstance(x, dict):
        return {k: _sin_sello(v) for k, v in x.items() if k not in ("generated_at", "minutos_antes")}
    if isinstance(x, list):
        return [_sin_sello(v) for v in x]
    return x


def escribir_si_cambia(ruta: Path, datos) -> bool:
    """Escribe solo si cambio algo mas que la hora de generacion.

    Entre corridas del mismo dia los ratings no cambian; lo que se mueve son
    las bajas. Reescribir el archivo cada 30 minutos por el sello de hora
    llenaria el historial de git de commits identicos.
    """
    if ruta.exists():
        try:
            if _sin_sello(json.loads(ruta.read_text())) == _sin_sello(json.loads(json.dumps(datos))):
                return False
        except json.JSONDecodeError:
            pass
    escribir(ruta, datos)
    return True
