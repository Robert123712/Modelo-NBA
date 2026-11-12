# Video corto por partido

Prototipo: un video vertical (TikTok) en español por partido, armado solo con
los datos del simulador.

1. `modelo_nba/video.py` guarda `data/video/<game_id>.json` en cada corrida:
   victorias, histograma de márgenes, cinta de resultados y, por jugador, su
   mejor partido y cuánto gana su equipo cuando pasa de cierto número.
2. `guion.py` escoge las historias y escribe el texto. Sin IA: plantilla fija,
   todos los números salen del JSON.
3. `voz.py` genera la voz (edge-tts, es-MX) y los tiempos por palabra.
4. `remotion/` es la plantilla animada (React). Renderiza 1080×1920 a 30 fps.

```bash
pip install edge-tts
(cd remotion && npm install)
python hacer.py ../data/video/<game_id>.json --metricas ../data/edgebook-metrics.json
```

Red necesaria: `a.espncdn.com` (fotos y logos) y `speech.platform.bing.com` (voz).
