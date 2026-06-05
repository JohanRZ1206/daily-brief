# Cómo grabar la demo

## Probar sin claves (modo demo)

```bash
python src/main.py --demo
```

Verás el digest simulado por consola, sin necesidad de API key ni feeds reales.

## Probar de verdad

1. `cp .env.example .env` y pon tu `ANTHROPIC_API_KEY` (y opcionalmente el bot de Telegram).
2. `cp config.example.json config.json` y ajusta tus feeds.
3. `python src/main.py` → genera el resumen real y lo manda a Telegram.

## Grabar el GIF

- **Windows:** [ShareX](https://getsharex.com/) → grabar región → exportar a GIF.
- Plano ideal: terminal ejecutando `python src/main.py` + el digest llegando a tu Telegram a las 8:00.

Guarda el GIF como `docs/demo.gif` y enlázalo en el README (ya hay un hueco).

## Captura del workflow de n8n

Importa `workflow.json`, captura el lienzo (Schedule → Execute → Code → Telegram)
y guárdala como `docs/n8n-workflow.png`.
