"""Vigilante: corre la prediccion a :15 y :45 dentro de un mismo job de Actions.

GitHub no garantiza los cron: en este repo dispara el programado solo 3-4 veces
al dia, a horas irregulares, y la regla de la oficial (ultima corrida con 60
minutos de anticipacion) necesita una corrida unos 75 minutos antes de cada
partido. Un job puede durar hasta 6 horas, asi que este se queda vivo ~5 horas,
corre en cada turno y publica. Al terminar, el workflow se relanza a si mismo;
el cron horario queda de respaldo por si la cadena se rompe.

Fuera de la ventana de partidos solo espera. Si la prediccion falla tres
turnos seguidos, sale con error y no se relanza: una cadena que falla en
bucle es peor que esperar al respaldo y que alguien vea el error.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import time
import traceback

import pandas as pd

ET = "America/New_York"
DURACION = dt.timedelta(hours=5, minutes=15)
TURNOS = (15, 45)
FALLAS_MAXIMAS = 3


def siguiente_turno(ahora: pd.Timestamp) -> pd.Timestamp:
    """El siguiente :15 o :45 estrictamente despues de `ahora`."""
    base = ahora.floor("h")
    for h in (0, 1):
        for m in TURNOS:
            t = base + pd.Timedelta(hours=h, minutes=m)
            if t > ahora:
                return t
    raise AssertionError("inalcanzable")


def en_ventana(ahora: pd.Timestamp) -> bool:
    """10:00 a 01:59 hora del Este: cubre T-75 del primer partido y el ultimo."""
    h = ahora.tz_convert(ET).hour
    return h >= 10 or h < 2


def publicar() -> None:
    subprocess.run(["git", "add", "data/"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("Sin cambios que publicar", flush=True)
        return
    ahora = pd.Timestamp.now(tz="UTC")
    msg = f"Proyecciones {ahora.tz_convert(ET).date()} {ahora:%H:%MZ}"
    subprocess.run(["git", "commit", "-q", "-m", msg], check=True)
    for intento in range(4):
        if (subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"]).returncode == 0
                and subprocess.run(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0):
            return
        time.sleep(2 ** (intento + 1))
    raise RuntimeError("No se pudo publicar despues de 4 intentos")


def turno() -> None:
    from .diario import predecir

    print(pd.Timestamp.now(tz="UTC").isoformat(), predecir(), flush=True)
    publicar()


def main() -> int:
    fin = pd.Timestamp.now(tz="UTC") + DURACION
    fallas = 0
    primero = True
    while True:
        ahora = pd.Timestamp.now(tz="UTC")
        if not primero:
            t = siguiente_turno(ahora)
            if t > fin:
                break
            time.sleep(max(0.0, (t - ahora).total_seconds()))
        primero = False
        if not en_ventana(pd.Timestamp.now(tz="UTC")):
            continue
        try:
            turno()
            fallas = 0
        except Exception:  # se reporta y se sigue; tres seguidas cortan
            traceback.print_exc()
            fallas += 1
            if fallas >= FALLAS_MAXIMAS:
                print(f"{fallas} fallas seguidas; se detiene sin relevo", flush=True)
                return 1
    salida = os.environ.get("GITHUB_OUTPUT")
    if salida:
        with open(salida, "a") as f:
            f.write("relevo=true\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
