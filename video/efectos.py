"""Efectos de sonido (sin musica): un barrido en cada cambio de bloque y un
golpe cuando cae cada numero. Se sintetizan con ffmpeg, sin archivos externos,
y se mezclan debajo de la voz.

    efectos.mezclar(tiempos, voz.wav, salida.wav)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

AR = 44100
# Los cues que llevan golpe: el numero llega en pantalla en ese instante.
GOLPES = {"cuenta", "veredicto", "numero", "sube0", "sube1", "remate", "link", "comenta"}
VOLUMEN = {"barrido": 0.32, "golpe": 0.5, "ding": 0.28}


def _sintetizar(dir_: Path) -> dict[str, Path]:
    dir_.mkdir(parents=True, exist_ok=True)
    recetas = {
        # Ruido rosa filtrado que sube y baja: "whoosh" de 0.4 s.
        "barrido": "anoisesrc=d=0.42:c=pink:r={ar},highpass=f=500,lowpass=f=6000,"
                   "afade=t=in:d=0.26:curve=exp,afade=t=out:st=0.26:d=0.16,volume=1.6",
        # Golpe grave con clic: seno que cae de 140 a 50 Hz en 0.18 s.
        "golpe": "aevalsrc='0.9*sin(2*PI*(50*t+450*(1-exp(-t*18))/18))*exp(-t*16)"
                 "+0.25*sin(2*PI*1800*t)*exp(-t*90)':d=0.25:s={ar}",
        # Campanita corta para el cierre.
        "ding": "aevalsrc='0.5*sin(2*PI*1320*t)*exp(-t*9)+0.25*sin(2*PI*1980*t)*exp(-t*12)':d=0.45:s={ar}",
    }
    rutas = {}
    for nombre, f in recetas.items():
        r = dir_ / f"{nombre}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f.format(ar=AR),
                        "-ac", "2", "-ar", str(AR), str(r)], check=True)
        rutas[nombre] = r
    return rutas


def linea_de_tiempo(tiempos: dict) -> list[tuple[str, float]]:
    eventos = []
    for i, e in enumerate(tiempos["escenas"]):
        if i > 0:
            eventos.append(("barrido", max(0.0, e["ini"] - 0.22)))
        for cue, t in e["cues"].items():
            if cue in GOLPES:
                eventos.append(("ding" if cue == "link" else "golpe", t))
    return sorted(eventos, key=lambda x: x[1])


def mezclar(tiempos: dict, voz: Path, salida: Path) -> Path:
    sfx = _sintetizar(salida.parent / "sfx")
    eventos = linea_de_tiempo(tiempos)
    entradas = ["-i", str(voz)]
    filtros = []
    for k, (nombre, t) in enumerate(eventos, start=1):
        entradas += ["-i", str(sfx[nombre])]
        ms = int(round(t * 1000))
        filtros.append(f"[{k}:a]volume={VOLUMEN[nombre]},adelay={ms}|{ms}[e{k}]")
    mezcla = "[0:a]" + "".join(f"[e{k}]" for k in range(1, len(eventos) + 1))
    filtros.append(f"{mezcla}amix=inputs={len(eventos) + 1}:duration=first:normalize=0[s]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", ";".join(filtros),
                    "-map", "[s]", "-ar", str(AR), "-ac", "2", str(salida)], check=True)
    return salida
