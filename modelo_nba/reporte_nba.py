"""Reporte oficial de lesiones de la NBA.

La liga publica un PDF cada 15 minutos en dia de partido
(`Injury-Report_2026-10-20_03_00PM.pdf`, hora del Este) con Out, Doubtful,
Questionable, Probable y Available por jugador. Es mas fino y mas a tiempo que
el roster de ESPN, que solo dice "Out" o "Day-To-Day" y no marca a los two-way
mandados a la G League (Harkless, DET, el dia inaugural: ESPN activo, el
reporte Out).

El PDF se lee por posicion de las palabras: el texto plano pega nombres
("BostonCeltics") y un motivo largo se parte en renglones arriba y abajo del
jugador.
"""

from __future__ import annotations

import datetime as dt
import io
import re

import pandas as pd
import requests

from .datos import clave_nombre

INDICE = "https://official.nba.com/nba-injury-report-{temporada}-season/"
PATRON = re.compile(
    r"https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf"
)
ET = "America/New_York"
AGENTE = {"User-Agent": "Mozilla/5.0 (modelo-nba)"}

# Lo que dice el reporte -> probabilidad de jugar. Mismo criterio que ESPN.
PROB = {"out": 0.0, "doubtful": 0.25, "questionable": 0.5, "probable": 0.9, "available": 1.0}
COLUMNAS = ("fecha", "hora", "partido", "equipo", "jugador", "estado", "motivo")


def _temporada(fecha: dt.date) -> str:
    inicio = fecha.year if fecha.month >= 8 else fecha.year - 1
    return f"{inicio}-{str(inicio + 1)[2:]}"


def reportes(html: str) -> list[tuple[pd.Timestamp, str]]:
    """(hora de publicacion, url) de cada reporte en el indice, ordenados."""
    out = []
    for m in PATRON.finditer(html):
        dia, h, mi, ampm = m.groups()
        hora = int(h) % 12 + (12 if ampm == "PM" else 0)
        t = pd.Timestamp(f"{dia} {hora:02d}:{mi}").tz_localize(ET)
        out.append((t, m.group(0)))
    return sorted(set(out))


def _columnas(palabras: list[dict]) -> dict[str, float] | None:
    """Donde empieza cada columna, por la posicion de su encabezado."""
    inicio = {}
    for w in palabras:
        t = w["text"]
        if t == "Game" and "fecha" not in inicio:
            inicio["fecha"] = w["x0"]
        elif t == "Time":
            inicio["hora"] = w["x0"] - 32
        elif t == "Matchup":
            inicio["partido"] = w["x0"]
        elif t == "Team":
            inicio["equipo"] = w["x0"]
        elif t == "Player":
            inicio["jugador"] = w["x0"]
        elif t == "Current":
            inicio["estado"] = w["x0"]
        elif t == "Reason":
            inicio["motivo"] = w["x0"]
    return inicio if len(inicio) == len(COLUMNAS) else None


def _renglones(palabras: list[dict], inicio: dict[str, float]) -> list[dict]:
    """Agrupa por altura y reparte las palabras en sus columnas."""
    bordes = sorted(inicio.items(), key=lambda x: x[1])
    filas: dict[float, dict[str, list[str]]] = {}
    for w in palabras:
        top = round(w["top"])
        clave = next((k for k in filas if abs(k - top) <= 2), top)
        col = None
        for nombre, x in bordes:
            if w["x0"] >= x - 2:
                col = nombre
        if col:
            filas.setdefault(clave, {}).setdefault(col, []).append(w["text"])
    return [
        {"top": top, **{c: " ".join(v) for c, v in cols.items()}}
        for top, cols in sorted(filas.items())
    ]


def parse_pdf(contenido: bytes) -> pd.DataFrame:
    """Una fila por jugador listado: fecha, partido, equipo, jugador, estado.

    `df.attrs["sin_reporte"]` trae los equipos que aun no entregan ("NOT YET
    SUBMITTED"): de esos no se puede leer nada y se sigue con ESPN.
    """
    import pdfplumber

    filas: list[dict] = []
    sin_reporte: list[tuple] = []
    arrastre: dict[str, str] = {}  # sigue de una pagina a la siguiente
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        inicio = None
        for pagina in pdf.pages:
            palabras = pagina.extract_words(x_tolerance=1.5)
            encabezado = [w["top"] for w in palabras if w["text"] == "Matchup"]
            inicio = _columnas(palabras) or inicio
            if inicio is None:
                continue
            tope = encabezado[0] + 3 if encabezado else 0
            for r in _renglones([w for w in palabras if w["top"] > tope], inicio):
                if r.get("fecha", "").startswith("Page") or any("Report:" in str(v) for v in r.values()):
                    continue
                for c in ("fecha", "hora", "partido", "equipo"):
                    if r.get(c):
                        arrastre[c] = r[c]
                texto = " ".join(r.get(c, "") for c in ("jugador", "estado", "motivo"))
                if "NOT YET SUBMITTED" in texto:
                    sin_reporte.append((arrastre.get("fecha"), arrastre.get("equipo")))
                    continue
                jugador, estado = r.get("jugador", ""), r.get("estado", "")
                motivo = r.get("motivo", "")
                if jugador and estado and "," in jugador:
                    apellido, nombre = [x.strip() for x in jugador.split(",", 1)]
                    # El motivo solo del renglon del jugador: uno largo se parte
                    # arriba y abajo y no hay forma segura de saber de quien es
                    # cada pedazo. El modelo solo usa el estado.
                    filas.append({**{c: arrastre.get(c) for c in ("fecha", "hora", "partido", "equipo")},
                                  "jugador": f"{nombre} {apellido}", "estado": estado.lower(),
                                  "motivo": motivo})
    df = pd.DataFrame(filas, columns=list(COLUMNAS))
    if len(df):
        df["fecha"] = pd.to_datetime(df.fecha, format="%m/%d/%Y", errors="coerce").dt.date
        df["clave"] = df.jugador.map(clave_nombre)
        df["prob_juega"] = df.estado.map(PROB)
    df.attrs["sin_reporte"] = [
        (pd.to_datetime(f, format="%m/%d/%Y", errors="coerce").date() if f else None, e)
        for f, e in sin_reporte
    ]
    return df


def ultimo(ahora: pd.Timestamp, fecha: dt.date, sesion: requests.Session | None = None) -> tuple[pd.DataFrame, str | None]:
    """El reporte mas reciente publicado antes de `ahora`, solo con `fecha`.

    Si la liga no responde, devuelve vacio y el modelo sigue con ESPN.
    """
    s = sesion or requests.Session()
    html = s.get(INDICE.format(temporada=_temporada(fecha)), headers=AGENTE, timeout=30).text
    candidatos = [(t, u) for t, u in reportes(html) if t <= ahora]
    if not candidatos:
        return pd.DataFrame(columns=list(COLUMNAS)), None
    hora, url = candidatos[-1]
    r = s.get(url, headers=AGENTE, timeout=60)
    r.raise_for_status()
    df = parse_pdf(r.content)
    del_dia = df[df.fecha == fecha].reset_index(drop=True)
    del_dia.attrs["sin_reporte"] = [e for f, e in df.attrs.get("sin_reporte", []) if f == fecha]
    return del_dia, hora.isoformat()


def aplicar(roster: list[dict], reporte: pd.DataFrame, equipo: str) -> list[dict]:
    """El roster de ESPN con el estado del reporte oficial encima.

    Si el equipo ya entrego reporte, manda el reporte: el listado toma su
    estado; el que no aparece esta disponible, salvo que ESPN lo tenga Out
    (por si un nombre no cruza, mejor no meter a un lesionado). Si el equipo
    no ha entregado, o no hay reporte, se queda lo de ESPN.
    """
    if reporte is None or reporte.empty or equipo in reporte.attrs.get("sin_reporte", []):
        return roster
    del_equipo = reporte[reporte.equipo.map(clave_nombre) == clave_nombre(equipo)]
    if del_equipo.empty and not (reporte.equipo.map(clave_nombre) == clave_nombre(equipo)).any():
        # Sin renglones del equipo: el reporte no lo menciona (no juega hoy o
        # no tiene a nadie listado). Sin mas informacion, se queda ESPN.
        return roster
    estado = dict(zip(del_equipo.clave, del_equipo.estado))
    out = []
    for r in roster:
        r = dict(r)
        e = estado.get(clave_nombre(r["nombre"]))
        if e is not None and e in PROB:
            r.update(estado=e, prob_juega=PROB[e], estado_conocido=True, fuente="nba")
        elif r["prob_juega"] > 0:
            r.update(estado="active", prob_juega=1.0, estado_conocido=True, fuente="nba")
        out.append(r)
    return out
