"""Efectos de sonido (sin musica): aire en cada cambio de bloque y unos
pocos sonidos en los momentos clave. Se sintetizan con ffmpeg, sin archivos externos,
y se mezclan debajo de la voz.

    efectos.mezclar(tiempos, voz.wav, salida.wav)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

AR = 44100
# Pocos sonidos y cada uno con su papel: aire en los cambios de bloque, un golpe
# grave solo para el numero del gancho, un "bloop" cuando sube la llave, teclas
# al escribirse la palabra y una campana suave al final.
VOLUMEN = {"aire": 0.16, "impacto": 0.42, "bloop": 0.22, "tecla": 0.14, "campana": 0.2}


def _sintetizar(dir_: Path) -> dict[str, Path]:
    dir_.mkdir(parents=True, exist_ok=True)
    recetas = {
        # Aire: ruido cafe filtrado, entra y sale despacio (0.55 s).
        "aire": "anoisesrc=d=0.55:c=brown:r={ar},highpass=f=300,lowpass=f=3200,"
                "afade=t=in:d=0.32:curve=qsin,afade=t=out:st=0.32:d=0.23:curve=qsin,volume=3",
        # Impacto: golpe grave y redondo, sin clic.
        "impacto": "aevalsrc='sin(2*PI*(46*t+38*(1-exp(-t*14))/14))*exp(-t*7)*min(1\\,t*400)':d=0.7:s={ar},"
                   "lowpass=f=260",
        # Bloop: dos notas cortas que suben.
        "bloop": "aevalsrc='0.6*sin(2*PI*587*t)*exp(-t*22)*min(1\\,t*300)"
                 "+0.6*sin(2*PI*880*max(0\\,t-0.09))*exp(-max(0\\,t-0.09)*16)*gt(t\\,0.09)':d=0.45:s={ar}",
        # Tecla: un toque seco y agudo de 20 ms.
        "tecla": "anoisesrc=d=0.03:c=white:r={ar},highpass=f=2200,lowpass=f=7000,afade=t=out:st=0.004:d=0.024",
        # Campana: dos notas suaves con cola larga.
        "campana": "aevalsrc='0.45*sin(2*PI*784*t)*exp(-t*4.5)*min(1\\,t*200)"
                   "+0.4*sin(2*PI*1175*max(0\\,t-0.12))*exp(-max(0\\,t-0.12)*4)*gt(t\\,0.12)':d=1.1:s={ar}",
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
        c = e["cues"]
        if i > 0:
            eventos.append(("aire", max(0.0, e["ini"] - 0.3)))
        if e["tipo"] == "gancho3" and "cuenta" in c:
            eventos.append(("impacto", c["cuenta"] + 1.0))  # cuando el numero termina de subir
        if e["tipo"] == "decide" and "sube0" in c:
            eventos.append(("bloop", c["sube0"]))
        if e["tipo"] == "cta":
            if "comenta" in c:  # una tecla por letra, al ritmo en que se escribe
                n = len(e["props"].get("palabra", "")) or 8
                eventos += [("tecla", c["comenta"] + 0.05 + 0.6 * k / n) for k in range(n)]
            if "link" in c:
                eventos.append(("campana", c["link"]))
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
