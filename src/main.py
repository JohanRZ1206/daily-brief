"""
Daily Brief — resumen diario de tus fuentes RSS, resumido con IA, a tu Telegram.

Lee una lista de feeds RSS desde config.json, recoge los artículos recientes,
los resume con la API de Claude y te manda un digest limpio por Telegram.

Modos de ejecución:
  - Standalone:  python src/main.py            (recoge, resume y envía a Telegram)
  - Desde n8n:   python src/main.py --json      (imprime el digest en JSON; n8n lo entrega)
  - Sin red/API: python src/main.py --demo       (datos y resumen simulados, para probar/demo)

Arquitectura: Python hace la lógica (RSS + IA); n8n o cron se encargan de
programarlo (cada mañana). El mismo código vale para script suelto o workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Dependencias ligeras con aviso amigable si faltan.
try:
    import requests
    from dotenv import load_dotenv
except ImportError as exc:  # pragma: no cover
    print(
        "Falta una dependencia. Instala todo con:\n"
        "    pip install -r requirements.txt\n"
        f"Detalle: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

# En Windows la consola suele usar cp1252 y rompe al imprimir emojis. Forzamos UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"

# Modelo de Claude. claude-opus-4-8 es el más capaz; puedes cambiarlo por uno
# más barato (p.ej. claude-haiku-4-5) poniendo ANTHROPIC_MODEL en tu .env.
DEFAULT_MODEL = "claude-opus-4-8"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(
            "No existe config.json. Copia config.example.json a config.json y "
            "pon tus feeds RSS.",
            file=sys.stderr,
        )
        sys.exit(1)
    with CONFIG_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def fetch_feed_items(feeds: list[str], max_per_feed: int) -> list[dict]:
    """Descarga cada feed RSS y devuelve los artículos más recientes."""
    import feedparser  # import perezoso: solo se necesita en modo real

    items: list[dict] = []
    for url in feeds:
        print(f"→ Leyendo feed: {url}", file=sys.stderr)
        parsed = feedparser.parse(url)
        source = parsed.feed.get("title", url)
        for entry in parsed.entries[:max_per_feed]:
            items.append(
                {
                    "title": entry.get("title", "(sin título)"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:500],
                    "source": source,
                }
            )
    return items


def build_prompt(items: list[dict]) -> str:
    """Construye el texto que mandamos a Claude con los artículos."""
    lines = ["Artículos de hoy:\n"]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. [{it['source']}] {it['title']}\n   {it['summary']}\n   {it['link']}")
    return "\n".join(lines)


def summarize_with_claude(items: list[dict]) -> str:
    """Resume los artículos en un digest breve usando la API de Claude."""
    import anthropic  # import perezoso: solo se necesita en modo real

    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno

    system = (
        "Eres un asistente que crea un resumen diario de noticias en español. "
        "Devuelve un digest claro y escaneable en TEXTO PLANO (sin Markdown, sin "
        "asteriscos). Agrupa por temas si tiene sentido, máximo una línea por "
        "artículo, e incluye el enlace al final de cada punto. Sé conciso."
    )
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": build_prompt(items)}],
    )
    return next((b.text for b in response.content if b.type == "text"), "").strip()


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    """Envía el digest a Telegram. Trocea si supera el límite de 4096 caracteres."""
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram corta a 4096; partimos en trozos por si el digest es largo.
    chunks = [message[i : i + 3800] for i in range(0, len(message), 3800)] or [message]
    ok = True
    for chunk in chunks:
        try:
            resp = requests.post(
                api,
                data={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  ! Error enviando a Telegram: {exc}", file=sys.stderr)
            ok = False
    return ok


def demo_items() -> list[dict]:
    return [
        {"title": "OpenAI presenta una nueva API de agentes", "link": "https://ejemplo.com/1",
         "summary": "Permite orquestar tareas multi-paso con herramientas.", "source": "TechDemo"},
        {"title": "Python 3.14 mejora el rendimiento del intérprete", "link": "https://ejemplo.com/2",
         "summary": "Optimizaciones en el GIL y arranque más rápido.", "source": "PyNews"},
        {"title": "n8n añade nodos nativos de IA", "link": "https://ejemplo.com/3",
         "summary": "Integración directa con modelos de lenguaje en workflows.", "source": "AutoWeekly"},
    ]


def demo_summary(items: list[dict]) -> str:
    """Resumen simulado (sin llamar a la API) para probar y grabar la demo."""
    lines = ["📰 Tu resumen diario (DEMO)\n"]
    for it in items:
        lines.append(f"• {it['title']} — {it['link']}")
    return "\n".join(lines)


def run(demo: bool, json_mode: bool) -> None:
    if demo:
        items = demo_items()
        digest = demo_summary(items)
    else:
        load_dotenv(BASE_DIR / ".env")
        config = load_config()
        items = fetch_feed_items(config["feeds"], config.get("max_items_per_feed", 5))
        if not items:
            print("No se encontraron artículos en los feeds.", file=sys.stderr)
            return
        digest = summarize_with_claude(items)

    payload = {
        "digest": digest,
        "item_count": len(items),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    # Modo JSON: lo consume n8n (u otro proceso). No envía nada.
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # Modo standalone: enseña el digest y lo manda a Telegram si hay credenciales.
    print("\n" + digest + "\n")

    if demo:
        return  # en demo no enviamos a Telegram salvo que el usuario tenga .env

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        if send_telegram(token, chat_id, digest):
            print("📨 Digest enviado por Telegram.")
    else:
        print(
            "(No envié a Telegram: faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en .env)",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumen diario de RSS con IA a Telegram.")
    parser.add_argument("--json", action="store_true",
                        help="Imprime el digest en JSON y no envía nada (para n8n).")
    parser.add_argument("--demo", action="store_true",
                        help="Usa datos y resumen simulados (sin red ni API key).")
    args = parser.parse_args()
    run(demo=args.demo, json_mode=args.json)


if __name__ == "__main__":
    main()
