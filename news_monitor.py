# -*- coding: utf-8 -*-
"""
news_monitor.py — Monitor de noticias para trading-platform.

Lee RSS feeds de news_sources.py, puntúa cada artículo según
las reglas de prioridad y guarda en news_cache.db.

Uso:
  python -X utf8 news_monitor.py          # loop continuo (cada 10 min)
  python -X utf8 news_monitor.py --once   # un ciclo y sale (para la API)
  python -X utf8 news_monitor.py --test   # muestra noticias sin guardar
"""

import sys
import os
import sqlite3
import datetime
import argparse
import time

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    print("[ERROR] feedparser no instalado — pip install feedparser", file=sys.stderr)
    sys.exit(1)

TRADING_DIR = os.environ.get("TRADING_DIR", "C:\\inversiones")
NEWS_DB     = os.path.join(TRADING_DIR, "news_cache.db")

sys.path.insert(0, TRADING_DIR)
from news_sources import FEEDS, RULES, FALLBACK_KEYWORDS, FALLBACK_PRIORITY

# ─── DB ───────────────────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    url          TEXT    UNIQUE,
    source       TEXT,
    market       TEXT,
    priority     TEXT    DEFAULT 'MEDIA',
    summary      TEXT,
    published_at TEXT,
    fetched_at   TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_news_fetched  ON news(fetched_at);
CREATE INDEX IF NOT EXISTS idx_news_market   ON news(market);
CREATE INDEX IF NOT EXISTS idx_news_priority ON news(priority);
"""

def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(DDL)
    conn.commit()
    return conn


# ─── SCORING ──────────────────────────────────────────────────────────────────

def _texto(entry: dict) -> str:
    return (
        entry.get("title", "") + " " +
        entry.get("summary", "") + " " +
        entry.get("description", "")
    ).lower()


def clasificar(entry: dict) -> tuple[str, str] | None:
    """
    Devuelve (market, priority) o None si la noticia no es relevante.
    """
    texto = _texto(entry)

    for rule in RULES:
        if any(kw in texto for kw in rule["any"]):
            return rule["market"], rule["priority"]

    # Fallback: al menos contiene keyword general
    if any(kw in texto for kw in FALLBACK_KEYWORDS):
        return "general", FALLBACK_PRIORITY

    return None


def parse_fecha(entry: dict) -> str:
    """Extrae fecha de publicación en ISO format."""
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published:
        try:
            return datetime.datetime(*published[:6]).isoformat()
        except Exception:
            pass
    return datetime.datetime.utcnow().isoformat()


# ─── CICLO PRINCIPAL ──────────────────────────────────────────────────────────

def run_cycle(conn: sqlite3.Connection, test_mode: bool = False) -> int:
    """
    Procesa todos los feeds. Devuelve número de noticias nuevas insertadas.
    """
    nuevas = 0

    for feed_cfg in FEEDS:
        url    = feed_cfg["url"]
        source = feed_cfg["source"]

        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"  [{source}] Error fetch: {e}")
            continue

        entradas = feed.entries[:20]  # máximo 20 por feed por ciclo
        print(f"  [{source}] {len(entradas)} entradas")

        for entry in entradas:
            resultado = clasificar(entry)
            if resultado is None:
                continue

            market, priority = resultado
            title   = entry.get("title", "")[:400]
            url_art = entry.get("link", "")[:500]
            summary = entry.get("summary", "")[:800]
            pub_at  = parse_fecha(entry)

            if test_mode:
                print(f"    [{priority:7}] [{market}] {title[:80]}")
                nuevas += 1
                continue

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO news
                       (title, url, source, market, priority, summary, published_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (title, url_art, source, market, priority, summary, pub_at),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    nuevas += 1
            except sqlite3.Error as e:
                print(f"    [DB Error] {e}")

    if not test_mode:
        conn.commit()

    return nuevas


def limpiar_antiguas(conn: sqlite3.Connection, dias: int = 7):
    """Elimina noticias con más de N días para no crecer indefinidamente."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=dias)).isoformat()
    conn.execute("DELETE FROM news WHERE fetched_at < ?", (cutoff,))
    conn.commit()


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Monitor de noticias — trading-platform")
    parser.add_argument("--once", action="store_true", help="Un ciclo y sale")
    parser.add_argument("--test", action="store_true", help="Muestra resultados sin guardar")
    parser.add_argument("--interval", type=int, default=600, help="Segundos entre ciclos (default: 600)")
    args = parser.parse_args()

    conn = init_db(NEWS_DB)
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[news_monitor] Iniciado {ahora} | DB: {NEWS_DB}")

    if args.test:
        print(f"[news_monitor] Modo TEST — no se guarda en DB\n")
        run_cycle(conn, test_mode=True)
        conn.close()
        return

    ciclo = 0
    while True:
        ciclo += 1
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{ts}] Ciclo #{ciclo}")

        nuevas = run_cycle(conn)
        print(f"  → {nuevas} noticias nuevas insertadas")

        # Limpiar cada 10 ciclos
        if ciclo % 10 == 0:
            limpiar_antiguas(conn)
            print(f"  → Limpieza: eliminadas noticias >7 días")

        if args.once:
            break

        print(f"  Próximo ciclo en {args.interval}s...")
        time.sleep(args.interval)

    conn.close()
    print(f"[news_monitor] Finalizado")


if __name__ == "__main__":
    main()
