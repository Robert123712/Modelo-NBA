"""Frases del gancho: que no suene siempre igual.

Cada opcion es (lo que se dice, lo que va en el letrero). {ap} es el apellido
de la figura. Hay frases para partido parejo, para favorito claro y generales;
se escoge con el game_id, asi los partidos del mismo dia salen distintos y el
mismo partido siempre da la misma frase. Sin numeros: el gancho no cita datos.
"""
from __future__ import annotations

MAX_LETRERO = 26

GENERALES = [
    ("Todo pasa por {ap}.", "TODO PASA POR {AP}"),
    ("Ojo con {ap}.", "OJO CON {AP}"),
    ("Hoy el partido tiene dueño: {ap}.", "EL DUEÑO: {AP}"),
    ("¿Alguien puede frenar a {ap}?", "¿QUIÉN FRENA A {AP}?"),
    ("La clave tiene nombre: {ap}.", "LA CLAVE: {AP}"),
    ("Todo depende de lo que haga {ap}.", "DEPENDE DE {AP}"),
    ("Hay un nombre que lo cambia todo: {ap}.", "EL NOMBRE: {AP}"),
    ("Si {ap} se prende, se acaba la discusión.", "SI SE PRENDE {AP}..."),
    ("Las computadoras ya hablaron, y hablan de {ap}.", "TODO SOBRE {AP}"),
]

PAREJOS = [  # el favorito gana menos del 58%
    ("Esto está parejísimo, y {ap} lo puede romper.", "{AP} ROMPE EL EMPATE"),
    ("Es un volado, y {ap} tiene la moneda.", "{AP} TIENE LA MONEDA"),
    ("Nadie se despega... salvo que {ap} diga otra cosa.", "¿LO DESEMPATA {AP}?"),
]

CLAROS = [  # el favorito gana 75% o mas
    ("¿Hay sorpresa, o {ap} les pasa por encima?", "¿SORPRESA O {AP}?"),
    ("Parece trámite... si {ap} cumple.", "SI {AP} CUMPLE"),
    ("El favorito es claro, pero el que manda es {ap}.", "MANDA {AP}"),
]

# NBA: cuando lo que destaca de la figura son rebotes o asistencias.
POR_STAT = {
    "reb": [
        ("Todo pasa por los rebotes de {ap}.", "LOS REBOTES DE {AP}"),
        ("El que controle los tableros gana, y ese es {ap}.", "LOS TABLEROS DE {AP}"),
        ("Ojo con {ap} debajo del aro.", "{AP} BAJO EL ARO"),
    ],
    "assists": [
        ("Todo pasa por las asistencias de {ap}.", "LAS ASISTENCIAS DE {AP}"),
        ("El que reparte el juego es {ap}.", "{AP} REPARTE"),
        ("Ojo con los pases de {ap}.", "LOS PASES DE {AP}"),
    ],
}


def gancho(ap: str, apodo: str, game_id, p_fav: float, stat: str | None = None) -> tuple[str, str]:
    """Devuelve (frase dicha, letrero) para la figura `ap` del favorito `apodo`."""
    semilla = int(game_id) if str(game_id).isdigit() else sum(map(ord, str(game_id)))
    if stat in POR_STAT:
        opciones = POR_STAT[stat]
    else:
        # Las frases de la situacion del partido (parejo o favorito claro) se suman a las generales.
        opciones = (PAREJOS if p_fav < 0.58 else CLAROS if p_fav >= 0.75 else []) + GENERALES
    # Ids seguidos (partidos del mismo dia) caen en frases seguidas: no se repiten.
    inicio = semilla % len(opciones)
    for frase, letrero in opciones[inicio:] + opciones[:inicio]:
        letrero = letrero.format(AP=ap.upper())
        if len(letrero) <= MAX_LETRERO:
            return frase.format(ap=ap), letrero
    # Un nombre largo no cabe en ningun letrero: se usa el equipo.
    return f"Todo pasa por el {apodo}.", f"TODO PASA POR {apodo.upper()}"
