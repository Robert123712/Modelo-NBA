# Props de jugador

Puntos, rebotes, asistencias y sus combinados (PRA, P+R, P+A) para la rotación
de 8 de cada equipo. Código en `modelo_nba/props.py`; se publican en
`data/latest.json → games[].props`.

## Cómo se calcula

Un prop es minutos por producción, y los dos se simulan **junto con el partido**
(las mismas 20,000 simulaciones del marcador):

1. **Minutos si juega.** Los mismos minutos proyectados del simulador, pero sin
   descontar la probabilidad de jugar: un prop se anula si el jugador no juega,
   así que al que está en duda se le proyecta su rol completo (y se marca
   `en_duda`).
2. **Ruido y paliza.** Cada simulación mueve los minutos ±6 (foul trouble,
   rachas). Por cada punto de margen arriba de 12, los titulares pierden 0.19
   minutos y se los lleva parejo el fondo de la banca (del noveno para abajo):
   en 2024-26, con 30+ de diferencia el titular jugó 4.9 minutos menos de lo
   proyectado, el sexto a octavo 0.8 más y el duodécimo en adelante 7.3 más.
   Detalle en `docs/MINUTOS.md`.
3. **Puntos amarrados al marcador.** Cada jugador se lleva su parte de los
   puntos de su equipo en esa simulación, según su tasa por posesión y sus
   minutos. Si el equipo anota 130, sus jugadores anotan más.
4. **Rebotes y asistencias** salen de su tasa por posesión, por el ritmo del
   partido, ajustada por lo que permite el rival en sus últimos 25 partidos.
5. **Tasas.** Por 100 posesiones en cancha, con memoria de 60 partidos (vida
   media) y encogidas hacia la liga con 300 posesiones ficticias.
6. **Mezcla.** La media final combina la simulación con el promedio de la
   temporada y el de los últimos 10 partidos. Los pesos salen de mínimos
   cuadrados en 2024-25:

   | | Simulación | Temporada | Últimos 10 |
   | --- | ---: | ---: | ---: |
   | Puntos | 0.67 | 0.21 | 0.17 |
   | Rebotes | 0.57 | 0.24 | 0.21 |
   | Asistencias | 0.62 | 0.17 | 0.23 |

7. **Dispersión.** Con los minutos ya simulados, los puntos varían 2.4 veces lo
   de un conteo Poisson (un triple vale 3); rebotes y asistencias, 1.05.
8. **Combinados.** PRA, P+R y P+A se suman simulación por simulación, así que
   comparten minutos y marcador: salen correlacionados, no sumados a ciegas.

9. **Asistencias contra la posición.** Lo que cada defensa permite en
   asistencias a guardias, aleros y centros (posición de ESPN), comparado con
   lo que esos mismos jugadores suelen dar. Por eso no se infla por haber
   enfrentado a buenos pasadores. Memoria de 180 días y encogido hacia 1.
10. **Compañeros fuera.** Si falta alguien que jugó en los últimos 15 días, la
    mitad de las asistencias que producía se reparte entre los que juegan. Los
    minutos ya se redistribuían; esto suma el uso.

Por cada estadística se publica media, mediana, rango 80% (p10–p90) y una
escalera de P(over) en líneas .5, compacta: `{"desde": 9.5, "p": [...]}` de uno en uno. El abanico es amplio (±12 puntos, ±6 rebotes y asistencias, ±15 PRA) para cubrir la línea de cualquier casa, sin las líneas con menos de 0.5% de un lado. En el partido: spread ±15, total ±20, total por equipo ±12, 1ª mitad ±8/±10. Además, cada jugador
trae `insight`: una frase corta con lo que más mueve su prop hoy, solo si pasa
un umbral (1.5 puntos, 0.8 rebotes, 0.6 asistencias, 4 minutos) y solo con
efectos que el backtest validó.

## Defensa contra posición: lo que se probó

Es lo más popular en redes ("cuántos rebotes permite Boston a los SF"), así que
se probó en serio: por posición (G/F/C) y por rol (base creador, pívot, ala-pívot
abierto, tirador, alero, sacado de sus estadísticas). Las dos versiones van
encogidas y medidas contra lo esperado de cada jugador. Afinado en 2024-25 y
probado a ciegas en 2025-26:

| | Puntos | Rebotes | Asistencias |
| --- | ---: | ---: | ---: |
| Por posición, acierta la dirección | 51% | 50% | **52–53%** |
| Por rol, acierta la dirección | 52% | 51% | 52% |
| Error con el ajuste (2025-26) | sin cambio | sin cambio | 1.487 → 1.485 |

Solo en asistencias, y solo por posición, la señal se repite fuera de muestra.
En puntos y rebotes los números de "defensa contra posición" son ruido: unos
25 partidos con uno o dos jugadores por posición no alcanzan para separar la
defensa de la suerte. Ahí se queda el ajuste por equipo de la v1.

**Compañeros fuera** fue igual: en asistencias ayuda (acierta 53–55% cuando
alguien falta; error 1.599 → 1.593 a ciegas) y en rebotes no. En puntos, el
reparto del marcador ya sube la parte de los que quedan, pero esa subida no
acierta la dirección (47%), así que no se usa para explicar.

## Backtest

Walk-forward: cada día se calculan tasas y promedios con lo jugado antes; la
disponibilidad sale del box score (equivale a conocer los inactivos a T-60).
Se califican los 8 de cada rotación que jugaron, con al menos 5 partidos en la
temporada. Se afinó en 2024-25; **2025-26 es prueba ciega**, ~19,200
jugador-partido.

### Error medio absoluto (2025-26, a ciegas)

| | Modelo | Promedio de temporada | Últimos 10 |
| --- | ---: | ---: | ---: |
| Puntos | **4.94** | 5.14 | 5.12 |
| Rebotes | **1.98** | 2.03 | 2.06 |
| Asistencias | **1.48** | 1.52 | 1.53 |
| PRA | **6.32** | 6.68 | 6.61 |
| P+R | **5.84** | 6.12 | 6.08 |
| P+A | **5.40** | 5.66 | 5.62 |

En los primeros 5 partidos de cada jugador también gana (puntos 5.24 contra
5.36; PRA 6.89 contra 7.06).

### Calibración

Usando como "línea" el promedio de temporada redondeado a .5:

| P(over) del modelo | Puntos real | PRA real |
| --- | ---: | ---: |
| 0.27 | 0.28 | 0.28 |
| 0.36 | 0.37 | 0.36 |
| 0.43 | 0.42 | 0.42 |
| 0.52 | 0.51 | 0.50 |
| 0.57 | 0.56 | 0.55 |
| 0.64 | 0.67 | 0.65 |
| 0.77 | 0.78 | 0.78 |

El rango 80% cubre 83% en puntos y 82% en PRA. En rebotes y asistencias cubre
87–90% porque son enteros chicos: el rango incluye sus extremos.

### Lo que no se sabe

**No hay líneas históricas de props de las casas**, así que esto no dice si el
modelo le gana al mercado. La línea de una casa es más fina que el promedio de
temporada, con lesiones y noticias incluidas. Lo que sí dice el backtest es que
las probabilidades están bien calibradas y que la media es mejor que los
promedios simples. Para saber si hay ventaja, hay que guardar las líneas reales
y calificar contra ellas durante la temporada.

## Limitaciones

- Los minutos son el error más grande (MAE 4.9 minutos): rotaciones que cambia
  el coach, foul trouble, minutos restringidos tras lesión.
- Un jugador traspasado conserva sus tasas; el cambio de rol se ve hasta que
  juega con el nuevo equipo.
- Novatos y jugadores sin historial usan la tasa de la liga.

## Tendencias de defensa contra posición

Cada jugador de los props trae `tendencias`: las defensas que más le ceden a su
posición en puntos, rebotes, asistencias y triples, en el top 5 de 30, en la
temporada (la pasada si van menos de 5 partidos) y en los últimos 7. Es el
formato de redes ("DET cede los MÁS rebotes a SG"), con un máximo de 3 por
jugador.

ESPN solo da G, F o C. Las cinco posiciones salen de partir los **minutos** de
guardias por asistencias (PG/SG) y de aleros por rebotes (SF/PF) a la mitad;
un alero con 14+ rebotes y 3.5+ tapones por 100 posesiones cuenta como C. Así
cada posición pesa parecido, como en una alineación, y el ranking compara
defensas contra el mismo tipo de jugador.

Son **descriptivas**. Lo que se probó arriba aplica: en puntos y rebotes no
predicen mejor que el azar, así que la proyección no se mueve con ellas (solo
asistencias, con el ajuste validado).

## Seguimiento para reentrenar

La predicción oficial de cada partido (la de 60 minutos antes) guarda en
`data/oficiales/AAAA-MM-DD.json → props`, por jugador: media y rango 80% de
cada estadística, minutos proyectados, su promedio de temporada hasta ese día y
el contexto de la proyección (`ctx`: minutos con el roster sano, factor del
rival y de las bajas por estadística, posición y si estaba en duda). Cada
corrida cruza las oficiales ya jugadas con su box score y escribe
`data/props-record.json` (error contra el promedio de temporada, % dentro del
rango 80%, sesgo). No se muestra en Edgebook: es la base para reajustar la
mezcla, la dispersión y los ajustes de contexto cuando haya volumen (unas
semanas, ~1,000 jugadores-partido).
