"""Parametros afinados, versionados en el repo (params/).

Se guardan como JSON para que un cambio de calibracion se vea en un diff y
quede ligado a la version del modelo que lo uso.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from .ratings import Parametros
from .simulador import ParametrosSim

DIR = Path(__file__).resolve().parent.parent / "params"


def cargar_parametros(directorio: Path = DIR) -> tuple[Parametros, ParametrosSim]:
    pr, ps = Parametros(), ParametrosSim()
    f = directorio / "ratings.json"
    if f.exists():
        datos = json.loads(f.read_text())
        validos = {x.name for x in fields(Parametros)}
        pr = Parametros(**{k: v for k, v in datos.items() if k in validos})
    f = directorio / "simulador.json"
    if f.exists():
        ps = ParametrosSim.de_dict(json.loads(f.read_text()))
    return pr, ps


def guardar_parametros(pr: Parametros | None, ps: ParametrosSim | None, directorio: Path = DIR) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    if pr is not None:
        (directorio / "ratings.json").write_text(json.dumps(asdict(pr), indent=1) + "\n")
    if ps is not None:
        (directorio / "simulador.json").write_text(json.dumps(ps.a_dict(), indent=1) + "\n")
