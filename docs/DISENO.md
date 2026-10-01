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
| Props de jugadores | Fuera de la v1 |

## Datos

- **Histórico:** [hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data)
  (sportsdataverse). Son los box scores de ESPN en parquet, por temporada. Llegan por
  `raw.githubusercontent.com` y se actualizan diario a las 07:00 UTC durante la
  temporada.
- **Lo reciente:** la API pública de ESPN (scoreboard, summary, roster). Todo
  partido terminado que todavía no esté en hoopR se baja de ESPN y se guarda en
  `data/box/`. El parser del box se valida contra las tablas de hoopR en
  `tests/test_espn.py`, y coincide hasta en las posesiones.
- **Bajas:** el roster de ESPN trae `injuries[].status` con "Out" o "Day-To-Day".
  "Out" quita al jugador. "Day-To-Day" multiplica sus minutos esperados por 0.6 y
  deja un aviso en el partido. El reporte oficial de la NBA (Questionable,
  Doubtful, Probable) queda para la fase 3.
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
- **Reparto.** Los disponibles se reparten 240 minutos proporcional a su base,
  con tope de 40 por jugador. Así se redistribuyen los minutos de una baja.
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

### 4. Mercados (`mercados.py`)

Para cada partido se publica una escalera de líneas alrededor de la del modelo,
porque la línea de la casa casi nunca coincide con la del modelo:

- Spread de ±8 puntos y total de ±10.
- Team totals de ±6.
- Primera mitad: spread de ±5 y total de ±6.

En líneas enteras existe el push. Su probabilidad es `1 − casa[L] − visita[−L]`.

## Registro y calificación

- **Cuándo corre.** El cron va a :15 y :45 entre 15:00 y 04:45 UTC. Para un
  tip-off a las :00 o :30, la corrida queda a 75 minutos, así que aguanta hasta
  15 minutos de retraso del cron.
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

- Reporte oficial de lesiones de la NBA (PDF) para Questionable/Doubtful/Probable.
- Métricas para el récord de Edgebook (`edgebook-metrics.json`), calificando las
  oficiales.
- Ritmo y localía por equipo (altura de Denver y Utah), viajes y 3 partidos en 4
  noches.
- Ratings con play-by-play (stints) en vez de a nivel partido.
