# Backtest

Es walk-forward con ajuste diario: cada día se entrena con todo lo jugado antes y
se proyectan los partidos de ese día. Se comparan con la línea de cierre de
consenso (la mediana entre casas de The Odds API, vía hoopR) sobre los mismos
partidos.

- **Afinación:** hiperparámetros y simulador se ajustaron con 2023-24 y 2024-25.
- **Prueba:** 2025-26 se evaluó al final, a ciegas.

La regla de reparto de minutos sí se comparó con 2024-25 y 2025-26 juntas, pero
las variantes quedaron dentro de 0.02 puntos entre sí, así que no se sobreajustó
por ahí.

## Supuesto importante

La disponibilidad sale del box score: un jugador cuenta si no fue baja por lesión
o ausencia. Eso equivale a conocer los inactivos a la hora del partido. En vivo,
a T-60, casi siempre se conocen, pero las bajas de último minuto harán que el
rendimiento real sea un poco peor que esto.

## Resultados: prueba ciega 2025-26 (1,326 partidos)

| Métrica | Modelo | Cierre |
| --- | ---: | ---: |
| Error medio del margen (pts) | 11.21 | 10.96 |
| Error medio del total (pts) | 14.82 | 14.50 |
| Brier del ganador | 0.2028 | 0.1972 |
| Log loss del ganador | 0.591 | 0.576 |
| Acierto del ganador | 68.9% | — |

La probabilidad del cierre se obtiene de su spread, con una desviación de 13.5
puntos.

**Calibración**

| Qué | Resultado |
| --- | --- |
| Intervalo de 80% del margen | cubre el 81.1% |
| Intervalo de 80% del total | cubre el 84.1% (un poco ancho; las colas reales son más pesadas que una normal) |
| Tiempo extra | modelo 4.8%, real 4.5% |
| Sesgo del margen | −0.24 pts (le da un poco de más al local) |
| Sesgo del total | +0.07 pts |
| Error del total de primera mitad | 9.76 pts |

**Probabilidad de ganar del local, por rango**

| Rango | n | Predicho | Real |
| --- | ---: | ---: | ---: |
| 0–20% | 70 | 15.5% | 11.4% |
| 20–35% | 150 | 28.2% | 24.7% |
| 35–50% | 309 | 43.0% | 42.7% |
| 50–65% | 341 | 57.4% | 61.6% |
| 65–80% | 308 | 71.6% | 72.4% |
| 80–100% | 148 | 86.4% | 85.8% |

**Contra la línea de cierre.** Cuenta el lado que el modelo prefiere cuando
difiere del cierre por al menos X puntos. No incluye pushes.

| Diferencia | Spread n | Spread acierto | Diferencia | Total n | Total acierto |
| --- | ---: | ---: | --- | ---: | ---: |
| ≥ 0 | 1,310 | 49.2% | ≥ 0 | 1,311 | 49.6% |
| ≥ 2 | 608 | 48.7% | ≥ 3 | 553 | 49.0% |
| ≥ 4 | 182 | 57.7% | ≥ 6 | 168 | 51.2% |
| ≥ 6 | 54 | 53.7% | ≥ 9 | 53 | 54.7% |

## Cómo leerlo

- **Está detrás del cierre, como era de esperar.** Le falta 0.25 puntos en el
  margen y 0.33 en el total. La línea de cierre es el mejor pronóstico público
  que existe. Un modelo que solo usa box scores públicos y no ve momios no
  debería ganarle de forma sistemática. Tampoco está lejos: la correlación con
  el cierre es de ~0.91 en el margen.
- **No hay ventaja demostrada contra la línea.** El 57.7% en diferencias de 4 o
  más puntos sale de 182 partidos y de probar varios cortes. Su error estándar
  es de ~3.7 puntos porcentuales, así que todavía no se distingue del azar. Hay
  que vigilarlo en vivo antes de creerlo.
- **La brecha con el cierre es la misma en entrenamiento que en prueba** (0.19
  contra 0.25 en el margen). El modelo no está sobreajustado.

## Entrenamiento 2023-24 y 2024-25 (referencia)

| Métrica | Modelo | Cierre |
| --- | ---: | ---: |
| Error medio del margen | 10.83 | 10.64 |
| Error medio del total | 14.52 | 14.13 |
| Brier del ganador | 0.2055 | 0.2005 |

## Parámetros elegidos (`params/ratings.json`)

| Parámetro | Valor | Nota |
| --- | --- | --- |
| Vida media de los ratings | 365 días | Más larga mejora el margen; 540 ya no aporta |
| Vida media del pace | 30 días | Corta mejora el total: el ritmo cambia rápido |
| λ jugador | 15 | 10–20 dan casi lo mismo |
| λ pace | 1 | |
| Efecto de equipo (sistema) | apagado | No mejoró nada con λ de 30 ni de 100 |
| Reparto de minutos | resta igual a todos cuando sobran; proporcional cuando faltan | |
| Memoria de minutos | 6 partidos | Para temporada regular ignora los playoffs |

Lo que más movió el error, de la búsqueda de hiperparámetros:

- **Margen:** pasó de 11.17 (valores iniciales) a 10.85. La mayor parte salió de
  bajar λ y alargar la memoria.
- **Total:** pasó de 14.98 a 14.60, con un pace de memoria corta.

## Reproducir

```bash
modelo-nba backtest --temporada 2026
modelo-nba calibrar --temporadas 2024 2025
```
