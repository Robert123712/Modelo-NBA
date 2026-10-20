# Modelo NBA: diseño

Simulador de partidos NBA que publica proyecciones para Edgebook, con el mismo
cable que MLB y NFL: corre en GitHub Actions, publica `data/edgebook-latest.json`
y Edgebook solo lo lee, lo valida y lo cruza con ESPN.

## Decisiones

| Tema | Decisión |
| --- | --- |
| Lenguaje | Python 3.11 |
| Mercados v1 | Ganador, spread, total, team totals, primera mitad (ganador, spread, total) |
| Predicción que se califica | La última generada con ≥ 60 minutos de anticipación al tip-off |
| Momios | No entran al modelo. Las líneas de cierre solo sirven para calificar |
| Props de jugadores | Puntos, rebotes, asistencias y combinados, rotación de 8 (`docs/PROPS.md`) |

## Datos

- **Histórico:** [hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data)
  (sportsdataverse). Son los box scores de ESPN en parquet, por temporada. Llegan por
  `raw.githubusercontent.com` y se actualizan diario a las 07:00 UTC durante la
  temporada.
- **Lo reciente:** la API pública de ESPN (scoreboard, summary, roster). Todo
  partido terminado que todavía no esté en hoopR se baja de ESPN y se guarda en
  `data/box/`. El parser del box se valida contra las tablas de hoopR en
  `tests/test_espn.py`, y coincide hasta en las posesiones.
- **Bajas:** manda el reporte oficial de la NBA (`reporte_nba.py`), el PDF que
  la liga publica cada 15 minutos con Out, Doubtful, Questionable, Probable y
  Available. Cada corrida toma el más reciente. Probabilidad de jugar: Out 0,
  Doubtful 0.25, Questionable 0.5, Probable 0.9. Si el equipo aún no entrega su
  reporte, o la liga no responde, se usa el roster de ESPN ("Out" o
  "Day-To-Day", este último a 0.6). Un jugador que ESPN tiene Out y no aparece
  en el reporte se queda fuera, por si su nombre no cruzó. El reporte sí ve lo
  que ESPN no: los two-way mandados a la G League.
- **Líneas de cierre:** el consenso de hoopR, que es la mediana entre casas de
  The Odds API. Solo se usan para el backtest y el récord.
- `stats.nba.com` no se usa porque bloquea IPs de nube, GitHub Actions incluido.

La temporada se nombra como en ESPN: `2027` es la 2026-27.

## Modelo

### 1. Ratings por jugador (`ratings.py`)

Cada partido da dos observaciones, una por cada ofensiva:

```
100·pts/posesiones = μ_temporada + h·localía
                   + Σ_ofensiva s_i·o_i − Σ_defensa s_j·d_j
                   + b2b de la ofensiva + b2b de la defensa
```

`s_i = minutos_i / minutos del partido` (los cinco en cancha suman 5). Es un RAPM
a nivel partido, ajustado como ridge con pesos por posesiones y decaimiento
temporal.

- **Dos pasadas.** La primera es ridge hacia cero. Después se ajusta un *box
  prior* (los coeficientes contra tasas de caja por 100 posesiones, encogidas
  hacia la media de la liga) y se vuelve a ajustar el ridge hacia ese prior.
- **μ por temporada.** Va penalizado hacia la temporada anterior, para que la
  primera semana no lo mueva el ruido.
- **Localía y back-to-back.** Salen de la misma regresión, no se ponen a mano.
- **Pace.** Base por temporada más el efecto de cada equipo, también con ridge.

### 2. Minutos (`minutos.py`)

- **Base de cada jugador.** Promedio exponencial de sus minutos en los partidos
  en que estuvo disponible, en cualquier equipo; un traspaso conserva su rol. Un
  DNP del coach cuenta como 0 minutos; un DNP por lesión no cuenta.
- **Reparto.** Entran los 11 disponibles de mayor base y se reparten 240
  minutos: si sobran, se le resta lo mismo a todos; si faltan (bajas), se
  reparten proporcional a la base. Tope de 40 por jugador. El tope de 11 importa
  en vivo: el roster de ESPN trae hasta 18 con los two-way, y cada uno de más le
  quitaba minutos a los titulares. En 2024-26 bajó el error de minutos de 5.07
  a 5.01 y dejó igual el de partidos.
- **Novatos.** Toman sus minutos según el turno del draft, medido en la clase
  2025: top 5, 27 min; 6–14, 15; 15–30, 9; segunda ronda, 6.

### 3. Simulación (`simulador.py`)

Son 20,000 partidos simulados por juego.

- **Mitades.** Cada simulación saca los puntos de cada equipo en cada mitad de
  una normal de 4 dimensiones. La covarianza se calibra con los residuos del
  backtest walk-forward, así que ya trae el error del modelo.
- **Cierre.** El reglamento termina empatado el 5.05% de las veces, cuando una
  normal da ~2.5%: el que va abajo por 1–3 al final busca empatar. Para
  reproducirlo, una fracción calibrada de los finales por 1, 2 y 3 se mueve a
  empate.
- **Tiempo extra.** Cada OT da unos 10.7 puntos por equipo (90% del ritmo del
  partido), y se juegan hasta que alguien gane.

### 3b. Los cuatro modelos y el árbitro (`motores/`, `ensamble.py`)

Además del modelo de jugadores hay tres modelos más:

- **Elo:** solo resultados.
- **Eficiencia de equipo:** ajustada por rival.
- **Cuatro factores:** tiro, pérdidas, rebote ofensivo y tiros libres.

Un árbitro combina sus márgenes con pesos que dependen de la fase de la temporada
y de las bajas, aprendidos en 2023-25. El total se queda con el modelo de
jugadores. El detalle, y por qué casi no mejora la precisión, está en
`docs/ENSAMBLE.md`.

### 4. Mercados (`mercados.py`)

Para cada partido se publica una escalera de líneas alrededor de la del modelo,
porque la línea de la casa casi nunca coincide con la del modelo:

- Spread de ±8 puntos y total de ±10.
- Team totals de ±6.
- Primera mitad: spread de ±5 y total de ±6.

En líneas enteras existe el push. Su probabilidad es `1 − casa[L] − visita[−L]`.

### 5. Props (`props.py`)

Minutos y producción de cada jugador se simulan dentro de las mismas
simulaciones del partido: los puntos de los jugadores salen del marcador de su
equipo y una paliza le quita minutos a los titulares. Detalle y backtest en
`docs/PROPS.md`.

## Registro y calificación

- **Cuándo corre.** Lo maneja `vigilante.yml`, porque GitHub solo disparaba el
  cron 3–4 veces al día. Un job de ~5 horas predice en cada :15 y :45 (entre
  10:00 y 01:59 hora del Este) y al terminar se relanza solo; un cron horario
  queda de respaldo. Para un tip-off a las :00 o :30, la corrida queda a 75
  minutos.
- **Qué se guarda.** `data/oficiales/AAAA-MM-DD.json` guarda la candidata oficial
  de cada partido. Cuando un partido entra a su última hora, ninguna corrida
  posterior lo reemplaza. Si ninguna corrida llegó a tiempo, queda la primera
  que hubo, marcada como `tardia`.
- **Partidos ya empezados.** Siguen en `edgebook-latest.json` con su predicción
  oficial congelada.
- **Cuándo se escribe.** Un archivo solo se reescribe si cambió algo más que la
  hora de generación. Así se evitan commits idénticos.

## Salida

- `data/edgebook-latest.json`: el envelope de Edgebook (`schema_version` 1.1,
  `sport: "NBA"`).
- `data/latest.json`: el detalle por partido. Trae la rotación proyectada, el
  desglose del margen y todas las escaleras de mercado.

### Cambios que necesita Edgebook

1. Agregar `"NBA"` a `SPORTS_WITH_MODEL`, con su URL y su workflow.
2. `projection.home_score/away_score` tienen `max(100)`, y en NBA se proyectan
   ~115. Hay que subir el límite (a 200, por ejemplo).
3. Agregar `SCORE_UNIT.NBA` (puntos).

## Backtest

Se ajusta cada día con lo jugado antes. La disponibilidad sale del box score
(equivale a conocer los inactivos a T-60); los minutos salen de la base previa
al partido. Los hiperparámetros se afinan en 2023-24 y 2024-25, y 2025-26 queda
como prueba.

Los resultados están en `docs/BACKTEST.md`.

## Pendiente

- Métricas para el récord de Edgebook (`edgebook-metrics.json`), calificando las
  oficiales.
- Ritmo y localía por equipo (altura de Denver y Utah), viajes y 3 partidos en 4
  noches.
- Ratings con play-by-play (stints) en vez de a nivel partido.
