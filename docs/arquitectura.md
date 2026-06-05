# Arquitectura

Lógica en Python (RSS + IA); programación en n8n o cron. El mismo código funciona
como script suelto o como pieza de un workflow automatizado.

```
        ┌─────────────────────────────────────────────┐
        │              ORQUESTACIÓN                     │
        │   n8n Schedule Trigger (cron 0 8 * * *)       │
        │   ó  cron del sistema                          │
        └───────────────────┬───────────────────────────┘
                            │ ejecuta cada mañana
                            ▼
   ┌─────────────────────────────────────────────────────┐
   │                  src/main.py (Python)                │
   │  1. Lee config.json (lista de feeds RSS)             │
   │  2. Descarga los feeds (feedparser)                  │
   │  3. Resume los artículos con la API de Claude        │
   │  4. Devuelve un digest en texto plano                │
   └───────────────┬───────────────────┬──────────────────┘
                   │                   │
       --json (n8n entrega)      standalone (Python envía)
                   │                   │
                   ▼                   ▼
       n8n: Telegram node       API de Telegram (requests)
```

## Decisiones de diseño

- **Imports perezosos:** `feedparser` y `anthropic` se importan solo cuando se
  usan (modo real). Así `--demo` arranca sin esas dependencias ni API key —
  ideal para probar y grabar la demo.
- **`--json` vs standalone:** una sola base de código sirve para que n8n entregue
  el digest (modo `--json`) o para que el propio Python lo mande (cron).
- **Resumen en texto plano:** se le pide a Claude texto sin Markdown para que
  Telegram no falle al formatear; el envío trocea mensajes de más de 4096 chars.
- **Modelo configurable:** `claude-opus-4-8` por defecto, cambiable por env
  (`ANTHROPIC_MODEL`) a uno más barato si el volumen lo pide.

## Coste

La API de Claude tiene coste por tokens. Un digest diario de pocos titulares es
muy barato; si quieres minimizar, usa `claude-haiku-4-5` vía `ANTHROPIC_MODEL`.
