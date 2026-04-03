"""
core.py — Módulo compartido para todos los scripts de inversiones.

Centraliza: constantes, acceso a APIs, helpers de formato, carga de portfolio.
Importar con: from core import *  o  from core import fetch_precio, titulo, ...

NO tiene lógica de negocio — solo infraestructura reutilizable.
"""

import json
import os
import datetime
import requests

# ─── CONSTANTES ──────────────────────────────────────────────────────────────

DIRECTORIO   = "C:\\inversiones"
LOGS_DIR     = os.path.join(DIRECTORIO, "logs")
PORTFOLIO_FILE = os.path.join(DIRECTORIO, "portfolio.json")

GAMMA_API    = "https://gamma-api.polymarket.com"
DATA_API     = "https://data-api.polymarket.com"
CLOB_API     = "https://clob.polymarket.com"

# Slugs oficiales de nuestras posiciones abiertas
SLUG_CEASEFIRE_APR15 = "us-x-iran-ceasefire-by-april-15-182-528-637"
SLUG_CONFLICT_JUN30  = "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725"

CONDITION_CEASEFIRE_APR15 = "0x773abaa5fe55e5cde51a261f444b7921652a4e059ead6b3be9fe56499c2d4609"
CONDITION_CONFLICT_JUN30  = "0x136f5a0c27a62cf9a2e40a4f48425e43d61b9571a53a2529372c0065f3218a73"

HOY = datetime.date.today().isoformat()

# ─── HELPERS DE FORMATO ───────────────────────────────────────────────────────

def sep(char="─", n=64):
    print(char * n)

def titulo(texto, char="═"):
    sep(char)
    print(f"  {texto}")
    sep(char)

def signo(val: float) -> str:
    return "+" if val >= 0 else ""

def pct(val: float) -> str:
    return f"{val:.1%}"

# ─── API POLYMARKET ───────────────────────────────────────────────────────────

def _parse_precios(raw) -> list[float]:
    """Convierte outcomePrices (str o list) a [yes, no] como floats."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    return [float(str(p).strip('"\'')) for p in raw]


def fetch_precio(slug: str) -> dict:
    """
    Precio YES y NO de un mercado por slug.
    Retorna: {"yes": 0.83, "no": 0.17, "vol": 7702981} o {"error": "..."}
    """
    try:
        r = requests.get(f"{GAMMA_API}/markets",
                         params={"slug": slug}, timeout=8)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        data = r.json()
        if not data:
            return {"error": "mercado no encontrado"}
        m = data[0]
        p = _parse_precios(m.get("outcomePrices", [0.5, 0.5]))
        return {
            "yes":      p[0],
            "no":       p[1],
            "vol":      float(m.get("volume", 0)),
            "titulo":   m.get("question", slug),
            "end_date": m.get("endDate", ""),
            "slug":     slug,
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_precio_por_condicion(condition_id: str, outcome: str = "no") -> tuple:
    """
    Precio de un mercado por conditionId via CLOB API.
    Retorna: (precio_float, fuente_str) o (None, error_str)
    """
    if not condition_id:
        return None, "sin condition_id"
    try:
        r = requests.get(f"{CLOB_API}/markets/{condition_id}", timeout=8)
        if r.status_code != 200:
            return None, f"CLOB error {r.status_code}"
        tokens = r.json().get("tokens", [])
        for t in tokens:
            if str(t.get("outcome", "")).upper() == outcome.upper():
                return float(t["price"]), "CLOB live"
        if len(tokens) >= 2:
            idx = 1 if outcome.lower() == "no" else 0
            return float(tokens[idx]["price"]), "CLOB live (idx)"
    except Exception as e:
        return None, f"error: {e}"
    return None, "no encontrado"


def fetch_trades(condition_id: str, limite: int = 200) -> list:
    """
    Últimos N trades de un mercado por conditionId.
    Retorna lista de dicts con: proxyWallet, side, outcome, size, price, timestamp, name
    """
    try:
        r = requests.get(f"{DATA_API}/trades",
                         params={"market": condition_id, "limit": limite},
                         timeout=15)
        if r.status_code != 200:
            return []
        return r.json() or []
    except Exception:
        return []


def fetch_mercado_completo(slug: str) -> dict:
    """
    Datos completos de un mercado: precio + outcomes + conditionId.
    Útil para mercados multi-outcome.
    """
    try:
        r = requests.get(f"{GAMMA_API}/markets",
                         params={"slug": slug}, timeout=8)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        data = r.json()
        if not data:
            return {"error": "no encontrado"}
        m = data[0]
        labels = m.get("outcomes", [])
        prices = _parse_precios(m.get("outcomePrices", []))
        if isinstance(labels, str):
            labels = json.loads(labels)
        return {
            "titulo":       m.get("question", slug),
            "slug":         slug,
            "condition_id": m.get("conditionId", ""),
            "outcomes":     [{"label": labels[i], "price": prices[i]}
                             for i in range(min(len(labels), len(prices)))],
            "vol":          float(m.get("volume", 0)),
            "end_date":     m.get("endDate", ""),
        }
    except Exception as e:
        return {"error": str(e)}


# ─── PORTFOLIO ────────────────────────────────────────────────────────────────

def cargar_portfolio() -> dict:
    """Carga portfolio.json. Lanza FileNotFoundError si no existe."""
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def posiciones_abiertas() -> list:
    """Retorna lista de posiciones Polymarket del portfolio."""
    return cargar_portfolio().get("posiciones_polymarket", [])


def calcular_pnl(precio_actual: float, entrada: float, shares: float) -> float:
    """P/L absoluto: (precio_actual - entrada) × shares"""
    return (precio_actual - entrada) * shares


def dias_restantes(fecha_resolucion: str) -> int:
    """Días hasta resolución desde hoy. fecha_resolucion: 'YYYY-MM-DD'"""
    return (datetime.datetime.strptime(fecha_resolucion, "%Y-%m-%d").date()
            - datetime.date.today()).days


# ─── LOGS ─────────────────────────────────────────────────────────────────────

def guardar_log(nombre_archivo: str, entrada: dict) -> str:
    """
    Añade `entrada` al log JSON diario en logs/.
    Retorna la ruta del archivo.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)
    ruta = os.path.join(LOGS_DIR, f"{nombre_archivo}_{HOY}.json")
    historial = []
    if os.path.exists(ruta):
        try:
            historial = json.loads(open(ruta, encoding="utf-8").read())
        except Exception:
            pass
    historial.append({**entrada, "timestamp": datetime.datetime.now().isoformat()})
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=2, ensure_ascii=False, default=str)
    return ruta


# ─── VERIFICACIÓN RÁPIDA ──────────────────────────────────────────────────────

if __name__ == "__main__":
    titulo("CORE.PY — TEST RÁPIDO")

    print("\n  Precios posiciones actuales:")
    for slug, nombre in [
        (SLUG_CEASEFIRE_APR15, "Ceasefire Apr15"),
        (SLUG_CONFLICT_JUN30,  "Conflict Jun30"),
    ]:
        p = fetch_precio(slug)
        if "error" in p:
            print(f"  {nombre}: ERROR — {p['error']}")
        else:
            print(f"  {nombre}: YES={pct(p['yes'])}  NO={pct(p['no'])}  "
                  f"Vol=${p['vol']:,.0f}")

    print("\n  Portfolio:")
    try:
        pos = posiciones_abiertas()
        for p in pos:
            print(f"  [{p['id']}] {p['mercado'][:50]}  "
                  f"entrada={p['precio_entrada_avg']}  "
                  f"shares={p['shares']}")
    except Exception as e:
        print(f"  Error: {e}")

    sep()
    print("  core.py OK")
