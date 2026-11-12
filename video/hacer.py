"""Un partido, de los datos del simulador al MP4.

    python hacer.py ../data/video/401909976.json [--metricas ../data/edgebook-metrics.json]

Pasos: guion (historias y texto) -> voz y tiempos -> fotos y logos de ESPN ->
render con Remotion. Deja el video en `salida/<game_id>.mp4`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

import guion
import guion_nfl
import narracion
import voz

AQUI = Path(__file__).parent
REMOTION = AQUI / "remotion"
ESPN = "https://a.espncdn.com/i"


def _bajar(url: str, destino: Path) -> None:
    if destino.exists():
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as r:
        destino.write_bytes(r.read())


def _ids(o) -> set[int]:
    if isinstance(o, dict):
        return ({o["athlete_id"]} if "athlete_id" in o else set()).union(*(_ids(v) for v in o.values()))
    if isinstance(o, list):
        return set().union(*(_ids(v) for v in o)) if o else set()
    return set()


def hacer(datos: Path, metricas: Path | None, salida: Path, manual: Path | None = None) -> Path:
    d = json.loads(datos.read_text())
    liga = d.get("liga", "nba")
    armar = guion_nfl.construir if liga == "nfl" else guion.construir
    g = armar(d, json.loads(metricas.read_text()) if metricas else None)
    if manual:
        g = narracion.aplicar(g, json.loads(manual.read_text()))
    trabajo = salida / str(d["game_id"])
    tiempos = voz.construir(g, trabajo)

    publico = REMOTION / "public"
    for a in _ids(tiempos["escenas"]):
        _bajar(f"{ESPN}/headshots/{liga}/players/full/{a}.png", publico / "jugadores" / liga / f"{a}.png")
    for e in tiempos["equipos"].values():
        _bajar(f"{ESPN}/teamlogos/{liga}/500/{e['abbr'].lower()}.png", publico / "logos" / liga / f"{e['abbr']}.png")
    shutil.copy(trabajo / "voz.wav", publico / "voz.wav")
    (REMOTION / "src" / "datos.json").write_text(json.dumps(tiempos, ensure_ascii=False))

    mp4 = salida / f"{d['game_id']}.mp4"
    orden = ["npx", "remotion", "render", "src/index.ts", "Partido", str(mp4.resolve()), "--crf=20"]
    # En la nube el navegador ya viene instalado; en otra maquina Remotion baja el suyo.
    if os.environ.get("VIDEO_NAVEGADOR"):
        orden.append(f"--browser-executable={os.environ['VIDEO_NAVEGADOR']}")
    subprocess.run(orden, cwd=REMOTION, check=True)
    return mp4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("datos", type=Path)
    ap.add_argument("--metricas", type=Path)
    ap.add_argument("--salida", type=Path, default=AQUI / "salida")
    ap.add_argument("--narracion", type=Path, help="Guion escrito aparte (ver narracion.py)")
    a = ap.parse_args()
    print(hacer(a.datos, a.metricas, a.salida, a.narracion))
