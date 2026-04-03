"""
alertas.py
Monitor automatico que se ejecuta cada hora.
Comprueba: precio SNDK, noticias ceasefire Iran, precio petroleo.
Escribe eventos criticos en alertas.log con timestamp.

Uso:
  python alertas.py            -- ejecutar una vez
  python alertas.py --loop     -- loop continuo cada hora (deja corriendo en terminal)
  python alertas.py --test     -- forzar escritura de alerta de prueba en log
"""
import sys
import time
import argparse
import logging
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LOG_FILE  = Path(__file__).parent / "alertas.log"
INTERVALO = 3600   # segundos entre checks (1 hora)

# Configuracion de alertas
SNDK_ALERTA_PRECIO = 620.0   # alerta si SNDK baja de este precio

KEYWORDS_CEASEFIRE = [
    "ceasefire", "cese al fuego", "peace deal", "iran deal",
    "iran agreement", "iran truce", "iran negotiations",
    "iran talks", "nuclear deal", "iran withdraw",
    "conflict ends", "end of conflict"
]

KEYWORDS_ESCALADA = [
    "iran attack", "iran missile", "hormuz closed", "hormuz blockade",
    "iran nuclear", "iran bomb", "iran strike", "us strike iran",
    "iran war", "houthi attack", "escalation iran"
]

RSS_FEEDS = [
    {"nombre": "Reuters",    "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"nombre": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
]

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)
logger = logging.getLogger("alertas")

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(console)


# ── Checks individuales ───────────────────────────────────────────────────────

def check_sndk():
    alertas = []
    try:
        t     = yf.Ticker("SNDK")
        info  = t.info
        precio = info.get("currentPrice") or info.get("regularMarketPrice")
        if precio is None:
            return alertas
        if precio <= SNDK_ALERTA_PRECIO:
            alertas.append({
                "tipo": "SNDK_ZONA_ENTRADA",
                "nivel": "CRITICO",
                "msg": f"SNDK en ${precio:.2f} — dentro de zona de entrada $580-$620 — EVALUAR COMPRA"
            })
        if precio <= 580:
            alertas.append({
                "tipo": "SNDK_BAJO_ZONA",
                "nivel": "CRITICO",
                "msg": f"SNDK en ${precio:.2f} — BAJO zona entrada minima $580 — REVISAR FUNDAMENTALES"
            })
    except Exception as e:
        logger.warning(f"check_sndk error: {e}")
    return alertas


def check_petroleo():
    alertas = []
    try:
        for nombre, ticker in [("Brent", "BZ=F"), ("WTI", "CL=F")]:
            t     = yf.Ticker(ticker)
            info  = t.info
            precio = info.get("regularMarketPrice") or info.get("currentPrice")
            if precio is None:
                continue
            if precio > 130:
                alertas.append({
                    "tipo": f"{nombre}_CRITICO",
                    "nivel": "ALTO",
                    "msg": f"{nombre} en ${precio:.2f} — nivel critico >$130 — riesgo de negociacion forzada Iran"
                })
            elif precio > 115:
                alertas.append({
                    "tipo": f"{nombre}_ALTO",
                    "nivel": "MEDIO",
                    "msg": f"{nombre} en ${precio:.2f} — nivel alto, presion creciente sobre conflicto Iran"
                })
            if precio < 90:
                alertas.append({
                    "tipo": f"{nombre}_BAJO",
                    "nivel": "INFO",
                    "msg": f"{nombre} en ${precio:.2f} — petroleo bajando, menor urgencia de resolucion Iran"
                })
    except Exception as e:
        logger.warning(f"check_petroleo error: {e}")
    return alertas


def parsear_titulos_rss(url, timeout=10):
    titulos = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AlertaBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return titulos
        root = ET.fromstring(r.content)
        for item in root.findall(".//item"):
            titulo = item.findtext("title", "")
            desc   = item.findtext("description", "")
            link   = item.findtext("link", "")
            titulos.append({"titulo": titulo, "desc": desc, "link": link})
    except Exception:
        pass
    return titulos


def check_noticias_iran():
    alertas = []
    for feed in RSS_FEEDS:
        items = parsear_titulos_rss(feed["url"])
        for item in items:
            texto = (item["titulo"] + " " + item["desc"]).lower()
            for kw in KEYWORDS_CEASEFIRE:
                if kw in texto:
                    alertas.append({
                        "tipo": "CEASEFIRE_MENCIONADO",
                        "nivel": "CRITICO",
                        "msg": f"[{feed['nombre']}] Posible ceasefire mencionado: '{item['titulo'][:80]}' | {item['link'][:60]}"
                    })
                    break
            for kw in KEYWORDS_ESCALADA:
                if kw in texto:
                    alertas.append({
                        "tipo": "ESCALADA_IRAN",
                        "nivel": "ALTO",
                        "msg": f"[{feed['nombre']}] Escalada detectada: '{item['titulo'][:80]}' | {item['link'][:60]}"
                    })
                    break
    return alertas


# ── Ciclo principal ───────────────────────────────────────────────────────────

def ejecutar_checks():
    logger.info("--- INICIO CHECK ---")
    todas_alertas = []

    todas_alertas.extend(check_sndk())
    todas_alertas.extend(check_petroleo())
    todas_alertas.extend(check_noticias_iran())

    if todas_alertas:
        for a in todas_alertas:
            nivel = a["nivel"]
            if nivel == "CRITICO":
                logger.critical(f"[{a['tipo']}] {a['msg']}")
            elif nivel == "ALTO":
                logger.error(f"[{a['tipo']}] {a['msg']}")
            elif nivel == "MEDIO":
                logger.warning(f"[{a['tipo']}] {a['msg']}")
            else:
                logger.info(f"[{a['tipo']}] {a['msg']}")
    else:
        logger.info("Sin alertas activas en este check.")

    logger.info(f"--- FIN CHECK ({len(todas_alertas)} alertas) ---")
    return todas_alertas


def loop_continuo():
    print(f"[alertas.py] Iniciando monitoreo continuo cada {INTERVALO//60} minutos.")
    print(f"[alertas.py] Log: {LOG_FILE}")
    print(f"[alertas.py] Ctrl+C para detener.\n")
    while True:
        try:
            alertas = ejecutar_checks()
            proxima = datetime.now().strftime("%H:%M:%S")
            print(f"  Proximo check en {INTERVALO//60} minutos...")
            time.sleep(INTERVALO)
        except KeyboardInterrupt:
            print("\n[alertas.py] Monitoreo detenido por el usuario.")
            break
        except Exception as e:
            logger.error(f"Error inesperado en loop: {e}")
            time.sleep(60)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Monitor de alertas de inversiones")
    parser.add_argument("--loop", action="store_true", help="Ejecutar en loop continuo cada hora")
    parser.add_argument("--test", action="store_true", help="Escribir alerta de prueba en log")
    args = parser.parse_args()

    if args.test:
        logger.info("[TEST] Alerta de prueba — sistema funcionando correctamente")
        print(f"Alerta de prueba escrita en {LOG_FILE}")
        return

    if args.loop:
        loop_continuo()
    else:
        alertas = ejecutar_checks()
        print(f"\nResumen: {len(alertas)} alerta(s) detectada(s).")
        print(f"Log guardado en: {LOG_FILE}")


if __name__ == "__main__":
    main()
