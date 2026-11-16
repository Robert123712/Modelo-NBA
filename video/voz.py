"""Voz y tiempos: del guion al audio y a la linea de tiempo que mueve el video.

Cada escena se sintetiza por separado con una voz neural en espanol de Mexico
(edge-tts, sin llave). El servicio regresa cuando empieza cada palabra; con eso
se arman los subtitulos palabra por palabra y los `cue` de las animaciones.

    python voz.py guion.json salida/   ->  salida/voz.wav, salida/tiempos.json
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import edge_tts

VOZ = os.environ.get("VIDEO_VOZ", "es-US-AlonsoNeural")
RITMO = os.environ.get("VIDEO_RITMO", "+36%")
COLA = 0.16  # silencio despues de la ultima palabra de cada escena
FPS = 30
# Pausas: la voz deja hasta ~0.7 s en cada "?" o "..." y medio segundo al
# arrancar cada escena. Con VIDEO_APRETAR=1 se recortan a PAUSA.
APRETAR = os.environ.get("VIDEO_APRETAR", "0") == "1"
PAUSA = 0.14
ARRANQUE = 0.04


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


async def _sintetizar(texto: str, mp3: Path) -> list[dict]:
    com = edge_tts.Communicate(texto, VOZ, rate=RITMO, boundary="WordBoundary",
                               proxy=os.environ.get("HTTPS_PROXY"))
    eventos = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                eventos.append({"ini": ch["offset"] / 1e7, "fin": (ch["offset"] + ch["duration"]) / 1e7,
                                "texto": ch["text"]})
    return eventos


def _palabras(narracion: list[dict], eventos: list[dict]) -> tuple[list[dict], dict]:
    """Reparte los tiempos de lo dicho entre las palabras que se ven."""
    # Cada palabra en pantalla ocupa un tramo de letras de lo que se dice.
    fichas, pos = [], 0
    for trozo in narracion:
        vistas, dichas = trozo["texto"].split(), trozo["voz"].split()
        largos = [len(_norm(w)) for w in dichas]
        if len(vistas) == len(dichas):
            grupos = [[k] for k in range(len(dichas))]
        elif len(vistas) == 1:
            grupos = [list(range(len(dichas)))]
        else:  # reparto parejo: no deberia pasar con el guion actual
            grupos = [[] for _ in vistas]
            for k in range(len(dichas)):
                grupos[min(k * len(vistas) // len(dichas), len(vistas) - 1)].append(k)
        for i, (w, g) in enumerate(zip(vistas, grupos)):
            n = sum(largos[k] for k in g)
            fichas.append({"texto": w, "a": pos, "b": pos + n, "cue": trozo["cue"] if i == 0 else None})
            pos += n
    # Cada evento de la voz cae en una posicion de ese mismo hilo de letras.
    total = "".join(_norm(t["voz"]) for t in narracion)
    cursor = 0
    for ev in eventos:
        n = _norm(ev["texto"])
        if not n:
            ev["pos"] = cursor
            continue
        k = total.find(n, cursor)
        if k < 0 or k - cursor > 12:
            k = cursor
        ev["pos"] = k
        cursor = k + len(n)
    palabras, cues, previo = [], {}, 0.0
    for f in fichas:
        dentro = [ev for ev in eventos if f["a"] <= ev["pos"] < max(f["b"], f["a"] + 1)]
        ini = dentro[0]["ini"] if dentro else previo
        fin = dentro[-1]["fin"] if dentro else previo + 0.05
        palabras.append({"texto": f["texto"], "ini": round(ini, 3), "fin": round(fin, 3)})
        if f["cue"]:
            cues[f["cue"]] = round(ini, 3)
        previo = fin
    return palabras, cues


def _apretar(mp3: Path, eventos: list[dict], wav: Path) -> list[dict]:
    """Quita el silencio inicial y deja cada pausa entre palabras en PAUSA como
    maximo. Regresa los eventos con los tiempos del audio recortado."""
    tramos, ini = [], max(0.0, eventos[0]["ini"] - ARRANQUE)
    for a, b in zip(eventos, eventos[1:]):
        if b["ini"] - a["fin"] > PAUSA:
            tramos.append((ini, a["fin"] + PAUSA / 2))
            ini = b["ini"] - PAUSA / 2
    tramos.append((ini, eventos[-1]["fin"] + 0.05))
    def mover(t: float) -> float:
        """Instante del audio original -> instante del recortado."""
        dentro = 0.0
        for x, y in tramos:
            if t < x:
                return dentro  # cae en una pausa quitada: se pega al siguiente tramo
            if t <= y:
                return dentro + t - x
            dentro += y - x
        return dentro
    filtros = "".join(f"[0:a]atrim={x:.3f}:{y:.3f},asetpts=PTS-STARTPTS[t{i}];" for i, (x, y) in enumerate(tramos))
    filtros += "".join(f"[t{i}]" for i in range(len(tramos))) + f"concat=n={len(tramos)}:v=0:a=1[s]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-filter_complex", filtros, "-map", "[s]",
                    "-ar", "44100", "-ac", "2", str(wav)], check=True)
    return [{**ev, "ini": round(mover(ev["ini"]), 3), "fin": round(mover(ev["fin"]), 3)} for ev in eventos]


def construir(guion: dict, salida: Path) -> dict:
    salida.mkdir(parents=True, exist_ok=True)
    partes, escenas, t0 = [], [], 0.0
    for i, esc in enumerate(guion["escenas"]):
        mp3 = salida / f"escena{i:02d}.mp3"
        texto = " ".join(t["voz"] for t in esc["narracion"])
        # El servicio a veces contesta vacio: se reintenta antes de rendirse.
        for intento in range(4):
            try:
                eventos = asyncio.run(_sintetizar(texto, mp3))
                break
            except edge_tts.exceptions.NoAudioReceived:
                if intento == 3:
                    raise
                time.sleep(1.5 * (intento + 1))
        wav = salida / f"escena{i:02d}.wav"
        fuente = mp3
        if APRETAR:
            corto = salida / f"escena{i:02d}-corto.wav"
            eventos = _apretar(mp3, eventos, corto)
            fuente = corto
        palabras, cues = _palabras(esc["narracion"], eventos)
        dur = eventos[-1]["fin"] + COLA
        # A cuadros enteros, para que audio y video no se despeguen.
        dur = round(dur * FPS) / FPS
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(fuente), "-af", f"apad,atrim=0:{dur}",
                        "-ar", "44100", "-ac", "2", str(wav)], check=True)
        partes.append(wav)
        escenas.append({
            **esc, "ini": round(t0, 4), "dur": round(dur, 4),
            "palabras": [{**p, "ini": round(p["ini"] + t0, 3), "fin": round(p["fin"] + t0, 3)} for p in palabras],
            "cues": {k: round(v + t0, 3) for k, v in cues.items()},
        })
        t0 += dur
    lista = salida / "partes.txt"
    lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c", "copy", str(salida / "voz.wav")], check=True)
    out = {**guion, "fps": FPS, "duracion": round(t0, 4), "escenas": escenas}
    (salida / "tiempos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    r = construir(json.load(open(sys.argv[1])), Path(sys.argv[2]))
    print("duracion", r["duracion"], "s")
    for e in r["escenas"]:
        print(f"{e['ini']:6.2f} {e['dur']:5.2f} {e['tipo']:9s} {e['cues']}")
