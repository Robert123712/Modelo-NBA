# Contrato `data/video/<game_id>.json` para el video NFL

Un archivo por partido, escrito por el simulador. Todo sale de las mismas
simulaciones (jugadores simulados DENTRO de cada partido simulado, para que
las probabilidades condicionales tengan sentido). Es el espejo del de NBA
(`Modelo-NBA/modelo_nba/video.py`, rama `claude/project-thread-00v22a`).

```json
{
  "liga": "nfl",
  "game_id": 401772945,
  "starts_at": "2026-11-13T01:15Z",
  "simulaciones": 10000,
  "equipos": {
    "home": {"abbr": "NYG", "nombre": "New York Giants"},
    "away": {"abbr": "WSH", "nombre": "Washington Commanders"}
  },
  "victorias": {"home": 6490, "away": 3500, "empates": 10},
  "marcador_medio": {"home": 23.4, "away": 19.8},
  "margen": {
    "desde": -31.5, "ancho": 3.0, "cuentas": [ ... 21 enteros, margen de casa ... ],
    "una_posesion": 0.411,
    "tiempo_extra": 0.040
  },
  "cinta": [{"gana": "NYG", "por": 7}, ... primeras 120 sims en orden ... ],
  "muestra": "hhahha... (ganador de las primeras 1000 sims: h, a, o e si empate)",
  "jugadores": {
    "home": [
      {
        "athlete_id": 4432577,
        "jugador": "Malik Nabers",
        "posicion": "WR",
        "media": {"pass_yds": 0, "pass_td": 0, "rush_yds": 1.2, "rec_yds": 80.3, "rec": 6.1, "td": 0.45},
        "sobre": {
          "pass_yds": {"250": 0.0, "300": 0.0},
          "pass_td": {"2": 0.0, "3": 0.0},
          "rush_yds": {"75": 0.0, "100": 0.0},
          "rec_yds": {"75": 0.48, "100": 0.33},
          "td": {"1": 0.36, "2": 0.08}
        },
        "mejor": {"stat": "rec_yds", "valor": 260, "td": 3, "gano": true},
        "eventos": [
          {"stat": "rec_yds", "umbral": 100, "texto": "100+ yardas por recepción",
           "p_evento": 0.33, "p_gana": 0.74, "p_gana_si_no": 0.60, "empuje": 0.09}
        ]
      }
    ],
    "away": [ ... ]
  }
}
```

Notas:

- `athlete_id` es el id de ESPN (columna `espn_id` de nflverse): con el se baja
  la foto. `abbr` es la de ESPN en mayusculas (WSH, no WAS), para el logo.
- `jugadores`: el QB titular, los 2 corredores y los 3-4 receptores/alas con
  mas volumen por lado. `media.td` son touchdowns anotados (carrera + recepcion),
  no los de pase.
- `mejor`: su mejor partido en todas las sims en su estadistica principal
  (QB `pass_yds`, RB `rush_yds`, WR/TE `rec_yds`), con si su equipo gano esa sim.
- `eventos`: solo los que pasan entre 12% y 60% de las sims; `p_gana` es la
  probabilidad de que gane SU equipo cuando el evento pasa; `empuje` = `p_gana`
  menos la probabilidad base de su equipo.
- `sobre`: probabilidad de igualar o pasar cada umbral. Los de arriba son el minimo.
- El record del modelo se toma de `data/edgebook-metrics.json`, sin cambios.
