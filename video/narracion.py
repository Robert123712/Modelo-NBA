"""Guion escrito a mano (o por Claude) encima del que arma la plantilla.

La plantilla decide que se ve en cada escena; este archivo cambia solo lo que
se dice y los rotulos. Antes de aceptarlo se revisa que cada numero que se
pronuncia exista ya en el guion de plantilla: nadie inventa cifras.

Formato: una lista con un objeto por escena, en el mismo orden:

    [{"props": {"titulo": "..."}, "narracion": [["texto", "cue o null"], ...]}, ...]

Los numeros se escriben con cifras; la voz los lee en palabras.
"""

from __future__ import annotations

import re

from numeros import decir

_NUM = re.compile(r"\d[\d,]*")


def voz(texto: str) -> str:
    """Lo que dice la voz: cifras en palabras y % como "por ciento"."""
    t = _NUM.sub(lambda m: decir(int(m.group().replace(",", ""))), texto)
    return t.replace("%", " por ciento")


def _numeros(o) -> set[int]:
    if isinstance(o, dict):
        return set().union(*(_numeros(v) for v in o.values())) if o else set()
    if isinstance(o, list):
        return set().union(*(_numeros(v) for v in o)) if o else set()
    if isinstance(o, bool):
        return set()
    if isinstance(o, (int, float)):
        return {int(round(o))}
    if isinstance(o, str):
        return {int(m.replace(",", "")) for m in _NUM.findall(o)}
    return set()


def aplicar(guion: dict, manual: list[dict]) -> dict:
    if len(manual) != len(guion["escenas"]):
        raise ValueError(f"El guion manual trae {len(manual)} escenas y la plantilla {len(guion['escenas'])}")
    for i, (esc, m) in enumerate(zip(guion["escenas"], manual)):
        permitidos = _numeros(esc["props"]) | _numeros([t["texto"] for t in esc["narracion"]]) \
            | {guion["simulaciones"]}
        cues = {t["cue"] for t in esc["narracion"] if t["cue"]}
        esc["props"].update(m.get("props", {}))
        if "narracion" not in m:
            continue  # esta escena se queda con lo que dice la plantilla
        trozos = []
        for texto, cue in m["narracion"]:
            extra = _numeros(texto) - permitidos
            if extra:
                raise ValueError(f"Escena {i} ({esc['tipo']}): {sorted(extra)} no sale de los datos: {texto!r}")
            if cue and cue not in cues:
                raise ValueError(f"Escena {i} ({esc['tipo']}): no existe el cue {cue!r} (hay {sorted(cues)})")
            # Cada cifra va en su propio trozo: al decirse ocupa varias
            # palabras y asi el subtitulo la marca completa.
            grupo: list[str] = []
            for w in texto.split() + [None]:
                if w is None or _NUM.search(w):
                    if grupo:
                        trozos.append({"texto": " ".join(grupo), "voz": " ".join(grupo), "cue": cue})
                        grupo, cue = [], None
                    if w is not None:
                        trozos.append({"texto": w, "voz": voz(w), "cue": cue})
                        cue = None
                else:
                    grupo.append(w)
        esc["narracion"] = trozos
    return guion
