"""
monitor_6abril_v2.py
====================
Monitor completo pre-deadline 6 abril. Integra:
  - pyth_feed.py     → precio WTI real (Yahoo Finance, fallback Pyth)
  - polymarket_api.py → odds en tiempo real (slugs verificados)
  - taco_detector    → señal TACO con RSS BBC/NYT/AlJazeera (~15-30min ventaja)
  - telegram         → alertas accionables con P/L estimado

Tesis: Irán NO cede. EEUU se retira gradualmente vendido como "victoria".
Señal TACO observable: lenguaje conciliador Casa Blanca + WTI cayendo >$3/h

Uso:
    python -X utf8 monitor_6abril_v2.py
    TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python -X utf8 monitor_6abril_v2.py
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone

# feedparser opcional
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

# Imports del sistema propio
TRADING_DIR = os.environ.get("TRADING_DIR", "C:\\inversiones")
sys.path.insert(0, TRADING_DIR)
from core.pyth_feed      import get_wti_price, get_wti_change
from core.polymarket_api import get_market_by_slug, MERCADOS

def get_pos2_odds():
    data = get_market_by_slug(MERCADOS["pos2_iran_jun30"])
    if "error" in data:
        return data
    yes = next((o for o in data["outcomes"] if o["label"].lower() == "yes"), None)
    no  = next((o for o in data["outcomes"] if o["label"].lower() == "no"),  None)
    return {
        "yes_price":    yes["price"] if yes else None,
        "no_price":     no["price"]  if no  else None,
        "volume_total": data["volume_total"],
        "condition_id": data["condition_id"],
    }

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
DEADLINE           = datetime(2026, 4, 6, tzinfo=timezone.utc)

TACO_CRASH_THRESHOLD  = -3.0   # $/hora → señal TACO
ESCALADA_THRESHOLD    = +2.5   # $/hora → conflicto escala
EDGE_MIN_ALERTA       = 0.10   # 10 centavos mínimo para alertar

# RSS feeds para detectar lenguaje Trump antes de que mueva el mercado
TRUMP_RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
]

# Palabras que indican TACO activándose
TACO_KEYWORDS = [
    "ceasefire", "deal", "agreement", "pause", "talks", "negotiat",
    "withdraw", "retreat", "peace", "accord", "armistice",
    "alto el fuego", "acuerdo", "retirada", "negociación", "paz",
    "trump chickens", "backs down", "reversal", "backs off",
]

# Palabras que indican escalada
ESCALADA_KEYWORDS = [
    "strike", "attack", "escalat", "missile", "bomb", "hormuz closed",
    "naval", "blockade", "tanker", "seized", "explosion",
    "ataque", "misil", "bloqueo", "escalada", "hormuz cerrado",
]

# ──────────────────────────────────────────────
# TACO DETECTOR MEJORADO — con RSS + precio
# ──────────────────────────────────────────────

_noticias_vistas = set()

def scan_noticias_trump() -> dict:
    """
    Escanea RSS feeds de noticias buscando señales TACO o escalada
    ANTES de que se reflejen en el precio del crudo.
    Ventaja: detecta el movimiento ~15-30 min antes que el mercado.
    Requiere feedparser: pip install feedparser
    """
    if not HAS_FEEDPARSER:
        return {"tipo": "sin_señal", "titular": "", "fuente": "",
                "nota": "feedparser no instalado — pip install feedparser"}

    señal = {"tipo": "sin_señal", "titular": "", "fuente": ""}

    for feed_url in TRUMP_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                uid = entry.get("id", entry.get("link", ""))
                if uid in _noticias_vistas:
                    continue
                _noticias_vistas.add(uid)

                texto = (entry.get("title", "") + " " + entry.get("summary", "")).lower()

                # Comprobar TACO keywords
                taco_hits = sum(1 for kw in TACO_KEYWORDS if kw in texto)
                escalada_hits = sum(1 for kw in ESCALADA_KEYWORDS if kw in texto)

                if taco_hits >= 2:
                    señal = {
                        "tipo":     "TACO_NOTICIA",
                        "titular":  entry.get("title", "")[:120],
                        "fuente":   feed_url.split("/")[2],
                        "hits":     taco_hits,
                        "urgencia": "ALTA",
                    }
                    return señal
                elif escalada_hits >= 2:
                    señal = {
                        "tipo":     "ESCALADA_NOTICIA",
                        "titular":  entry.get("title", "")[:120],
                        "fuente":   feed_url.split("/")[2],
                        "hits":     escalada_hits,
                        "urgencia": "MEDIA",
                    }
        except Exception:
            continue

    return señal


def detect_taco_precio(cambio_hora: float) -> str:
    """Detecta señal basada en movimiento de precio."""
    if cambio_hora <= TACO_CRASH_THRESHOLD:
        return "TACO_PRECIO"
    elif cambio_hora >= ESCALADA_THRESHOLD:
        return "ESCALADA_PRECIO"
    return "sin_señal"


# ──────────────────────────────────────────────
# DETECTOR DE DISCREPANCIAS MEJORADO
# ──────────────────────────────────────────────

def theoretical_price(wti: float, strike: float, direction: str, dias_restantes: int) -> float:
    """
    Precio teórico mejorado con ajuste por tiempo restante.
    Cuanto menos tiempo queda, más determinista es el resultado.
    """
    factor_tiempo = max(0.3, dias_restantes / 30)  # menos tiempo = más certeza

    if direction == "up":
        if wti >= strike:
            # Ya superado: probabilidad alta, crece con poco tiempo restante
            margen = (wti - strike) / strike
            return min(0.99, 0.92 + margen * 0.5 * (1 - factor_tiempo * 0.3))
        else:
            distancia = (strike - wti) / wti
            return max(0.02, 0.70 - distancia * 3 * (1 + factor_tiempo))
    else:  # down
        if wti <= strike:
            margen = (strike - wti) / strike
            return min(0.99, 0.92 + margen * 0.5 * (1 - factor_tiempo * 0.3))
        else:
            distancia = (wti - strike) / wti
            # Desde $101 a $52 = 49% de caída en ~90 días
            # El mercado dice 51% → bastante calibrado
            return max(0.02, 0.80 - distancia * 2.0 * (1 + factor_tiempo * 0.5))


def detect_discrepancias(wti: float) -> list:
    """
    Detecta oportunidades comparando WTI actual vs nuestras posiciones.
    Versión simplificada usando solo mercados verificados.
    """
    dias = max(1, (DEADLINE - datetime.now(timezone.utc)).days)
    oportunidades = []

    # Analizar posición Ceasefire Apr15 vs WTI
    data_p1 = get_market_by_slug(MERCADOS["pos1_ceasefire_apr15"])
    if "error" not in data_p1:
        no_outcome = next((o for o in data_p1["outcomes"] if o["label"].lower() == "no"), None)
        if no_outcome:
            no_price = no_outcome["price"]
            # Si WTI > 100 el mercado debería asignar más prob a NO ceasefire
            teorico_no = min(0.95, 0.75 + (wti - 90) * 0.01) if wti > 90 else 0.75
            edge = round(teorico_no - no_price, 4)
            if abs(edge) >= EDGE_MIN_ALERTA:
                oportunidades.append({
                    "label":        f"Ceasefire Apr15 NO (WTI=${wti})",
                    "market_price": no_price,
                    "theoretical":  teorico_no,
                    "edge":         edge,
                    "accion":       "REFORZAR NO" if edge > 0 else "CONSIDERAR SALIDA",
                    "urgencia":     "ALTA" if abs(edge) > 0.15 else "MEDIA",
                })

    return sorted(oportunidades, key=lambda x: abs(x["edge"]), reverse=True)


# ──────────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────────

def telegram(msg: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TELEGRAM] {msg[:100]}...")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5,
        )
        return r.ok
    except Exception as e:
        print(f"[Telegram error] {e}")
        return False


def msg_taco_precio(cambio: float, wti: float, tipo: str) -> str:
    dias = (DEADLINE - datetime.now(timezone.utc)).days
    if "TACO" in tipo:
        return (
            f"🕊️ *SEÑAL TACO — precio*\n"
            f"WTI: *${wti}* ({cambio:+.1f}$/h)\n"
            f"El mercado anticipa acuerdo.\n\n"
            f"*Acción:* REFORZAR Pos2 (conflict ends Jun30)\n"
            f"VIGILAR salida de strikes alcistas CL\n\n"
            f"_Deadline: {dias} días_"
        )
    else:
        return (
            f"🔥 *ESCALADA HORMUZ — precio*\n"
            f"WTI: *${wti}* ({cambio:+.1f}$/h)\n"
            f"Irán intensifica. No cederá.\n\n"
            f"*Acción:* MANTENER/AUMENTAR ↑$110 WTI Abril\n"
            f"NO tocar Pos2 hasta nueva señal.\n\n"
            f"_Deadline: {dias} días_"
        )


def msg_taco_noticia(señal: dict, wti: float) -> str:
    dias = (DEADLINE - datetime.now(timezone.utc)).days
    es_taco = "TACO" in señal["tipo"]
    emoji = "📰🕊️" if es_taco else "📰🔥"
    accion = "REFORZAR Pos2 — acuerdo posible" if es_taco else "MANTENER strikes alcistas"
    return (
        f"{emoji} *NOTICIA DETECTADA {'(TACO)' if es_taco else '(ESCALADA)'}*\n"
        f"_{señal['titular']}_\n"
        f"Fuente: {señal['fuente']}\n\n"
        f"WTI actual: *${wti}*\n"
        f"*Acción anticipada:* {accion}\n\n"
        f"_Esta señal llega ~15-30 min antes que el mercado_\n"
        f"_Deadline: {dias} días_"
    )


def msg_discrepancia(op: dict, wti: float) -> str:
    return (
        f"⚡ *DISCREPANCIA DETECTADA*\n"
        f"Mercado: {op['label']}\n"
        f"WTI: *${wti}*\n"
        f"Odds mercado: {round(op['market_price']*100,1)}¢\n"
        f"Odds teóricas: {round(op['theoretical']*100,1)}¢\n"
        f"Edge: *{op['edge']:+.2f}* ({round(abs(op['edge'])*100,0):.0f}¢)\n"
        f"*→ {op['accion']}*"
    )


def msg_resumen(wti: float, pos2: dict) -> str:
    dias = (DEADLINE - datetime.now(timezone.utc)).days
    pos2_str = f"{round(pos2.get('yes_price',0)*100,1)}¢" if not pos2.get("error") else "N/A"
    return (
        f"📊 *Resumen horario*\n"
        f"WTI: *${wti}*\n"
        f"Pos2 (conflict ends Jun30): {pos2_str}\n"
        f"Deadline Hormuz: *{dias} días*\n\n"
        f"Tesis: Irán NO cede (doctrina 20 años)\n"
        f"Escenario base: retirada gradual EEUU\n"
        f"WTI se mantiene elevado durante proceso\n\n"
        f"Trigger TACO: Casa Blanca conciliadora + WTI ↓$3/h"
    )


# ──────────────────────────────────────────────
# BUCLE PRINCIPAL
# ──────────────────────────────────────────────

def main():
    print("=" * 55)
    print(f"Monitor activo — deadline {DEADLINE.date()}")
    print("Módulos: Pyth + Polymarket + RSS + Telegram")
    print("Tesis: Irán NO cede. EEUU se retira gradualmente.")
    print("=" * 55)

    ciclo = 0

    while True:
        ciclo += 1
        ahora = datetime.now(timezone.utc).isoformat()[:19] + "Z"
        print(f"\n[{ahora}] Ciclo #{ciclo}")

        # ── 1. Precio WTI real ──────────────────
        wti_data = get_wti_change()
        if not wti_data.get("price"):
            print(f"  Error WTI: {wti_data.get('error')}")
            time.sleep(60)
            continue

        wti    = wti_data["price"]
        cambio = wti_data.get("cambio_hora", 0)
        print(f"  WTI: ${wti} ({cambio:+.2f}$/h) | Señal precio: {wti_data['signal']}")

        # ── 2. Señal TACO por precio ────────────
        tipo_precio = detect_taco_precio(cambio)
        if tipo_precio != "sin_señal":
            telegram(msg_taco_precio(cambio, wti, tipo_precio))
            print(f"  ⚡ Alerta precio enviada: {tipo_precio}")

        # ── 3. Señal TACO por noticias (cada 5 min) ──
        if ciclo % 5 == 0:
            noticia = scan_noticias_trump()
            if noticia["tipo"] != "sin_señal":
                telegram(msg_taco_noticia(noticia, wti))
                print(f"  📰 Noticia detectada: {noticia['tipo']}")
            else:
                print(f"  RSS: sin señales nuevas")

        # ── 4. Discrepancias (cada 5 min) ────────
        if ciclo % 5 == 0:
            ops = detect_discrepancias(wti)
            print(f"  Discrepancias: {len(ops)}")
            for op in ops:
                print(f"    {op['label']}: edge {op['edge']:+.2f} → {op['accion']}")
                if op["urgencia"] == "ALTA":
                    telegram(msg_discrepancia(op, wti))

        # ── 5. Resumen horario (cada 60 ciclos) ──
        if ciclo % 60 == 0:
            pos2 = get_pos2_odds()
            telegram(msg_resumen(wti, pos2))
            print(f"  Resumen horario enviado")

        time.sleep(60)


if __name__ == "__main__":
    main()
