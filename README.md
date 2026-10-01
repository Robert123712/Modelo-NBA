# Modelo NBA

Simulador de partidos NBA que publica proyecciones para
[Edgebook](https://github.com/Robert123712/edgebook). Por cada partido calcula:

- **Ganador**, con y sin tiempo extra.
- **Spread**, en escalera de líneas, con la probabilidad de push.
- **Total** y **total de cada equipo**.
- **Primera mitad**: ganador (con empate), spread y total.

Hace 20,000 simulaciones por partido. Corre en GitHub Actions y publica en `data/`.

El diseño completo está en [`docs/DISENO.md`](docs/DISENO.md).

## Cómo funciona, en corto

1. **Ratings por jugador.** Sale de quién estuvo en cancha y cuánto, con una
   regresión ridge sobre todos los partidos de las últimas temporadas, regularizada
   hacia lo que dice su box score.
2. **Minutos proyectados.** Con las bajas del día, los minutos de cada jugador se
   redistribuyen entre los disponibles.
3. **Puntos esperados de cada equipo.** Combina ratings, ritmo, localía y
   back-to-back.
4. **Monte Carlo.** Simula por mitades, con el cierre del reglamento (empates
   reales ~5%) y tiempos extra.

## Uso

```bash
pip install -e ".[dev]"
pytest -q

modelo-nba predecir                     # slate de hoy (hora del Este)
modelo-nba predecir --fecha 2026-10-21
modelo-nba backtest --temporada 2026    # walk-forward contra líneas de cierre
modelo-nba calibrar --temporadas 2024 2025
```

`HOOPR_LOCAL=/ruta/a/hoopR-nba-data` lee los parquet de un clon local en vez de
bajarlos.

## Salidas

| Archivo | Qué es |
| --- | --- |
| `data/edgebook-latest.json` | Envelope que lee Edgebook (mismo contrato que MLB y NFL) |
| `data/latest.json` | Detalle por partido: rotación proyectada, desglose y escaleras de mercado |
| `data/oficiales/AAAA-MM-DD.json` | La predicción que se califica: la última con ≥ 60 min de anticipación |
| `data/box/` | Box scores de ESPN que hoopR todavía no publica |

## Datos

- **Histórico:** box scores de ESPN vía
  [hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data).
- **Del día:** la API pública de ESPN (slate, rosters, bajas y box scores
  recientes).
- **Líneas de cierre:** el consenso de hoopR. Solo se usan para calificar; el
  modelo no lee momios.
