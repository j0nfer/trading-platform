"""
pyth_feed.py — Precio WTI en tiempo real
Fuente primaria: Yahoo Finance (CL=F futures)
Fuente secundaria: Pyth Network (misma que Polymarket — si accesible)

El WTI es el indicador clave para detectar señal TACO:
  - WTI cae >$3/hora → mercado anticipa acuerdo → señal TACO
  - WTI sube >$2.5/hora → escalada Hormuz → mantener posición NO
"""

import requests
import time
from datetime import datetime

# Pyth Network — fuente oficial de Polymarket para resolver mercados WTI
WTI_PRICE_ID = "0x00ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ac"
PYTH_URL = f"https://hermes.pyth.network/api/latest_price_feeds?ids[]={WTI_PRICE_ID}"

# Yahoo Finance — fallback robusto
YAHOO_URL = "https://query2.finance.yahoo.com/v8/finance/chart/CL=F"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

_cache = {"price": None, "ts": None, "ttl": 30}


def _from_pyth() -> dict | None:
    """Intenta obtener WTI desde Pyth Network."""
    try:
        r = requests.get(PYTH_URL, timeout=5)
        if r.status_code != 200:
            return None
        feed = r.json()[0]
        raw  = int(feed["price"]["price"])
        expo = int(feed["price"]["expo"])
        conf = int(feed["price"]["conf"])
        pub_t = int(feed["price"]["publish_time"])
        price = round(raw * (10 ** expo), 2)
        return {
            "price":       price,
            "confidence":  round(conf * (10 ** expo), 4),
            "timestamp":   datetime.utcfromtimestamp(pub_t).isoformat() + "Z",
            "age_seconds": int(time.time() - pub_t),
            "source":      "pyth",
            "from_cache":  False,
        }
    except Exception:
        return None


def _from_yahoo() -> dict | None:
    """Obtiene WTI desde Yahoo Finance (CL=F futures)."""
    try:
        r = requests.get(
            YAHOO_URL,
            params={"interval": "1m", "range": "1d"},
            headers=YAHOO_HEADERS,
            timeout=8,
        )
        if r.status_code != 200:
            return None
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        if not price:
            return None
        return {
            "price":       round(float(price), 2),
            "confidence":  None,
            "timestamp":   datetime.utcnow().isoformat() + "Z",
            "age_seconds": 0,
            "source":      "yahoo_finance",
            "from_cache":  False,
        }
    except Exception:
        return None


def get_wti_price(use_cache=True) -> dict:
    """
    Retorna precio WTI actual.
    Intenta Pyth primero, cae a Yahoo Finance si no disponible.
    """
    now = time.time()

    if use_cache and _cache["ts"] and (now - _cache["ts"]) < _cache["ttl"]:
        cached = _cache["price"].copy()
        cached["age_seconds"] = int(now - _cache["ts"])
        cached["from_cache"] = True
        return cached

    result = _from_pyth() or _from_yahoo()

    if result is None:
        return {"error": "Sin fuente disponible (Pyth + Yahoo fallaron)", "price": None}

    _cache["price"] = result.copy()
    _cache["ts"]    = now
    return result


def get_wti_change(window_minutes=60) -> dict:
    """
    Calcula cambio de precio en la última hora.
    Retorna cambio $/hora y señal TACO/escalada.
    """
    current = get_wti_price()
    if current.get("error") or not current["price"]:
        return {"error": current.get("error"), "cambio": None, "signal": "sin_señal"}

    price  = current["price"]
    cambio = 0.0

    if hasattr(get_wti_change, "_last_price"):
        elapsed_h = (time.time() - get_wti_change._last_ts) / 3600
        if elapsed_h > 0:
            cambio = (price - get_wti_change._last_price) / elapsed_h

    get_wti_change._last_price = price
    get_wti_change._last_ts    = time.time()

    signal = "sin_señal"
    if cambio <= -3.0:
        signal = "TACO_ACTIVANDO"
    elif cambio >= 2.5:
        signal = "ESCALADA_HORMUZ"

    return {
        "price":       price,
        "cambio_hora": round(cambio, 2),
        "signal":      signal,
        "timestamp":   current["timestamp"],
        "source":      current["source"],
    }


if __name__ == "__main__":
    print("Obteniendo precio WTI...")
    data = get_wti_price(use_cache=False)
    if data.get("error"):
        print(f"Error: {data['error']}")
    else:
        print(f"WTI: ${data['price']}  (fuente: {data['source']})")
        if data.get("confidence"):
            print(f"Confianza: ±${data['confidence']}")
        print(f"Timestamp: {data['timestamp']}")
