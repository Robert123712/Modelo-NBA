# Minutos: qué los mueve

Estudio de octubre de 2026 sobre el error de los minutos proyectados, que son
la base de los props. Respuesta: minutos reales − minutos esperados por el
simulador, para jugadores de rotación (10+ proyectados), temporada regular sin
tiempos extra. Se descubre en 2024-25 (18,207 partidos-jugador) y se confirma
a ciegas en 2025-26 (20,331). Un factor cuenta si sale en las dos temporadas
para el mismo lado, con corrección de Holm, y si mueve medio minuto o más.

## Factores

Regresión con todos los factores a la vez, errores agrupados por jugador.

| Factor | 2024-25 | 2025-26 | Veredicto |
| --- | ---: | ---: | --- |
| Titular en su partido anterior | +3.19 | +3.70 | Entra |
| Racha (últimos 3 − base, por 5 min) | +1.26 | +1.46 | Entra vía memoria corta |
| Primer partido tras perderse 3+ | −4.72 | −5.14 | Entra |
| Titular con bajas (por 10 min) | −0.50 | −0.71 | Entra |
| Nivel de la proyección (por 10 min) | −0.96 | −0.96 | Entra (encoge) |
| Primer partido tras traspaso | −3.23 | −5.48 | Entra (52 casos) |
| Primeros 5 partidos del año | −1.77 | −2.38 | Entra (238 casos) |
| Faltas por 36 (por falta) | −0.34 | −0.16 | Entra, chico |
| Veterano 31+ en back-to-back | −0.66 | −0.45 | Entra, evidencia media |
| Edad, back-to-back solo, 3 en 4, descanso, local, spread, profundidad del coach, novato, tanque, volatilidad | ≈ 0 | ≈ 0 | Fuera |

No hay sesgo propio por jugador: en un modelo mixto con intercepto por
jugador, su varianza sale cero. El error de un partido sigue siendo de ~6
minutos de desviación: es ruido del partido y por eso `sd_minutos` se queda en 6.

## Paliza

Minutos reales − proyectados según la diferencia final y el lugar en la
rotación (2024-26):

| Diferencia final | Titulares | 6° a 8° | 9° a 11° | 12° en adelante |
| --- | ---: | ---: | ---: | ---: |
| 0-4 | +0.2 | −0.1 | −1.2 | +1.6 |
| 15-19 | −2.1 | +0.5 | +1.0 | +3.5 |
| 30+ | −4.9 | +0.8 | +3.4 | +7.3 |

La pendiente de los titulares es 0.19 min por punto (no 0.27) y los minutos
se van al fondo de la banca, no al sexto hombre.

## Diseño factorial de las perillas

2^(7−2), resolución IV, 32 corridas con números aleatorios comunes. Efecto en
el error de minutos (promedio de las dos temporadas; negativo = mejora):

| Perilla | Cambio | Efecto |
| --- | --- | ---: |
| Vida media de los minutos | 6 → 3 partidos | −0.16 |
| Destino de la paliza | banca proporcional → del 9° para abajo | −0.07 |
| Umbral de paliza | 8 → 12 puntos | −0.05 |
| Pendiente de paliza | 0.27 → 0.19 | −0.05 |
| Tope de rotación | 11 → 10 | +0.03 |
| Arranque (K) | 0.5 → 2 | +0.02 |
| Ruido de minutos | 6 → 5 | +0.01 (CRPS +0.02) |

Barrido de la vida media con la paliza nueva: 1 → 5.02, 1.5 → 4.96, **2 →
4.95**, 2.5 → 4.97, 3 → 5.00, 4 → 5.05, 6 → 5.15 (error 2025-26).

## Lo que quedó

`minutos.CORRECCION` se ajustó en 2024-25 con todo el proceso (corregir →
repartir → paliza → residuo, por punto fijo) y se probó en 2025-26:

| Versión | Error de minutos 2024-25 | 2025-26 (a ciegas) |
| --- | ---: | ---: |
| Antes | 5.23 | 5.28 |
| Memoria 2 + paliza nueva | 4.89 | 4.95 |
| + correcciones | 4.80 | 4.85 |

Solo entra a props. En el backtest de 2025-26 (mismos partidos simulados,
18,529 jugador-partido con 5+ juegos en la temporada):

| | Antes | Ahora |
| --- | ---: | ---: |
| Error de minutos | 4.80 | 4.57 |
| Puntos (error) | 4.992 | 4.968 |
| Rebotes | 1.995 | 1.985 |
| Asistencias | 1.497 | 1.491 |
| PRA | 6.361 | 6.311 |
| Brier del over en la línea del promedio, puntos | 0.2354 | 0.2336 |
| Brier, PRA | 0.2327 | 0.2305 |

La mezcla final (simulación, temporada, últimos 10) se reajustó en 2024-25 con
los minutos nuevos y no cambió el error de 2025-26 (puntos −0.008, asistencias
+0.004), así que se quedó igual.

Al modelo del marcador no le sirvió: con los minutos nuevos, el error del
margen en 2025-26 pasó de 11.187 a 11.193 y el del total de 14.80 a 14.82. Se
queda con su memoria de 6 partidos y sin correcciones (`VIDA_MEDIA_MARCADOR`).

## Alineación titular del día

Con quién arranca hoy en vez de quién arrancó el partido anterior, y las
correcciones reajustadas igual en 2024-25 (`CORRECCION_ALINEACION`; titular
pesa +5.8 en vez de +2.4), el error de minutos en 2025-26 baja de 4.85 a
4.69. En vivo sale de la NBA (`alineaciones.py`); el equipo que todavía no
tiene alineación se queda con `CORRECCION`. Cada corrida publica en
`latest.json` el estado de cada equipo (`alineacion`: Expected, Confirmed o
null) y en cada prop si es titular.

