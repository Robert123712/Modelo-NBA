# Ensamble: cuatro modelos y un árbitro

## Qué es

El simulador tiene cuatro modelos. Cada uno ve el partido desde un ángulo
distinto:

| Modelo | Archivo | Qué mira |
| --- | --- | --- |
| Jugadores | `ratings.py` | Cuánto vale cada jugador y quién juega hoy (RAPM con box prior) |
| Elo | `motores/elo.py` | Solo quién le ganó a quién, por cuánto y dónde (versión FiveThirtyEight) |
| Eficiencia de equipo | `motores/equipos.py` | Puntos por posesión anotados y recibidos, ajustados por rival (estilo KenPom) |
| Cuatro factores | `motores/factores.py` | eFG%, pérdidas, rebote ofensivo y tiros libres; cada factor con su propia memoria y regresión a la media |

El **árbitro** (`ensamble.py`) combina los márgenes con pesos que dependen del
contexto:

- **Fase:** los juegos que lleva el equipo con menos en la temporada (menos de 10,
  de 10 a 29, o 30 o más).
- **Bajas:** la mayor fracción de minutos habituales que le falta a alguno de
  los dos equipos (15% o más cuenta como "con bajas").

Los pesos se aprenden de las predicciones walk-forward de 2023-24 y 2024-25. Son
pesos no negativos que suman 1, y los grupos con pocos partidos se encogen hacia
los pesos globales.

## Afinación de cada modelo (2023-24 y 2024-25)

| Modelo | Parámetros | Error medio del margen |
| --- | --- | ---: |
| Elo | K=25, localía 60, regreso 25% | 11.18 |
| Eficiencia de equipo | memoria de 90 días, λ=5 | 11.17 |
| Cuatro factores | memorias de 15 a 25 partidos | 11.21 |
| Jugadores | (ya afinado) | 10.83 |
| Cierre | | 10.64 |

Los modelos se correlacionan 0.90 a 0.96 entre sí. No piensan igual, pero casi.

## Lo que aprendió el árbitro

En el **margen**, casi todo el peso va al modelo de jugadores. La única excepción
útil es **media temporada con bajas**: 68% jugadores y 32% eficiencia de equipo.
Al inicio con plantilla completa le da 8% al Elo.

En el **total**, el árbitro empeoraba en la prueba (14.85 contra 14.80), así que el
total se queda con el modelo de jugadores.

## Prueba ciega 2025-26

| Margen | Error medio |
| --- | ---: |
| Jugadores solo | 11.206 |
| Elo | 11.53 |
| Eficiencia de equipo | 11.51 |
| Cuatro factores | 11.54 |
| Promedio simple de los 4 | 11.36 |
| Árbitro sin contexto | 11.206 |
| **Árbitro con contexto** | **11.196** |
| Línea de cierre | 10.96 |

La mejora es de 0.01 puntos: no se distingue del ruido. **El ensamble no hace más
preciso al simulador.** Los otros tres modelos leen los mismos marcadores que el
de jugadores, pero sin saber quién juega hoy, así que no le agregan información.

## Lo que se probó y no funcionó

- **El desacuerdo entre modelos como medidor de confianza.** Cuando los cuatro
  discrepan, el error del partido no es mayor; si acaso, sale menor.
- **El consenso contra la línea.** Cuando los cuatro contradicen al cierre en la
  misma dirección, aciertan 47% a 52%. No hay ventaja.
- **Errores sistemáticos por calendario.** Se probaron descanso, 3 partidos en 4
  noches, giras de visitante, altura (Denver y Utah) y final de temporada. Ninguno
  se repite de 2023-25 a 2025-26. El más prometedor (totales 3.6 puntos más bajos
  en los últimos 8 partidos, t=−3.8) desapareció en la prueba (−0.2).

## Por qué quedó en producción

Igual se publica lo que dice cada modelo (`latest.json → modelos` y el primer
factor de cada partido), y el árbitro decide el margen. No cuesta precisión: en
casi todos los grupos el resultado es el del modelo de jugadores. Además deja
ver cuándo los modelos discrepan, y el árbitro se puede re-entrenar con la
temporada nueva:

```bash
# Con backtests de las temporadas recientes (ver backtest.correr):
python -c "from modelo_nba import ensamble; ..."   # ensamble.ajustar(bt)
```

## Hallazgo lateral: el All-Star

hoopR marca los partidos de All-Star como temporada regular (EAST, LEB, STARS,
STRIPES…), con marcadores como 211-186 o minipartidos a 40 puntos. Eran 11 en 6
temporadas, y se estaban usando para calcular los ratings. Ahora se filtran: solo
cuentan los equipos con id 1 a 30 de ESPN, en `historico.py`, `datos.py` y
`diario.py`.
