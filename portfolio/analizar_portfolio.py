"""
analizar_portfolio.py
Resumen completo de portfolio: posiciones Polymarket, alertas de riesgo,
noticias Iran en tiempo real via RSS, precio SNDK, y historial de trades
con analisis de calibracion y aprendizaje.
"""
import sys, os
sys.path.insert(0, "C:\\inversiones")

import json
import argparse
import requests
import yfinance as yf
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PORTFOLIO_FILE  = Path("C:\\inversiones") / "portfolio.json"
HISTORIAL_FILE  = Path("C:\\inversiones") / "historial_trades.json"

RSS_FEEDS = [
    {"nombre": "Al Jazeera",        "url": "https://www.aljazeera.com/xml/rss/all.xml",                                              "nivel": "B", "idioma": "en"},
    {"nombre": "Reuters World",     "url": "https://feeds.reuters.com/Reuters/worldNews",                                             "nivel": "B", "idioma": "en"},
    {"nombre": "Reuters Business",  "url": "https://feeds.reuters.com/reuters/businessNews",                                          "nivel": "B", "idioma": "en"},
    {"nombre": "Reuters Markets",   "url": "https://feeds.reuters.com/reuters/marketsNews",                                           "nivel": "B", "idioma": "en"},
    {"nombre": "AP World",          "url": "https://rsshub.app/apnews/topics/world-news",                                             "nivel": "B", "idioma": "en"},
    {"nombre": "AP Intl",           "url": "https://rsshub.app/apnews/topics/apf-intlnews",                                           "nivel": "B", "idioma": "en"},
    {"nombre": "EFE Economia",      "url": "https://www.efe.com/efe/espana/economia/rss",                                             "nivel": "B", "idioma": "es"},
    {"nombre": "AFP/Google Iran",   "url": "https://news.google.com/rss/search?q=iran+war+ceasefire&hl=es&gl=ES&ceid=ES:es",          "nivel": "B", "idioma": "es"},
]

# Palabras clave para filtrar noticias relevantes al portfolio
KEYWORDS_IRAN = [
    "iran", "ceasefire", "hormuz", "khamenei", "trump iran",
    "tehran", "persian gulf", "houthi", "nuclear deal",
    "conflict ends", "strike iran", "sanctions iran",
    "cese al fuego", "conflicto iran", "petroleo", "petróleo",
    "crude oil", "brent", "wti", "fed rate", "recession", "recesion",
    "sndk", "sandisk", "middle east", "oriente medio"
]

# Señales que afectan a cada posición
IMPACTO_CEASEFIRE_APR15 = [
    "ceasefire", "cese al fuego", "peace", "paz", "deal", "acuerdo",
    "negotiations", "negociaciones", "trump iran", "april", "abril",
    "withdraw", "retirada", "truce", "tregua", "insider"
]
IMPACTO_CONFLICT_JUN30 = [
    "conflict ends", "fin del conflicto", "ceasefire", "bilateral",
    "june", "junio", "hormuz", "escalation", "escalada",
    "houthi", "nuclear", "sanctions", "sanciones", "oil", "petroleo"
]

CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

# Módulos avanzados (opcionales — fallan silenciosamente si no están disponibles)
try:
    from herramientas_avanzadas import calcular_indice_estres
    _HERRAMIENTAS_OK = True
except ImportError:
    _HERRAMIENTAS_OK = False

try:
    from sesgos_psicologicos import (detectar_sesgos_posicion,
                                     mostrar_sesgos_activos,
                                     recordatorio_del_dia)
    _SESGOS_OK = True
except ImportError:
    _SESGOS_OK = False


# ── Helpers de formato ───────────────────────────────────────────────────────

def sep(char="─", ancho=66):
    print(char * ancho)

def titulo(texto, char="═"):
    sep(char)
    print(f"  {texto}")
    sep(char)

def s(val):
    return "+" if val >= 0 else ""


# ── Carga portfolio ──────────────────────────────────────────────────────────

def cargar_portfolio():
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── Precio Polymarket ────────────────────────────────────────────────────────

def precio_polymarket(condition_id):
    if not condition_id:
        return None, "sin condition_id"
    try:
        r = requests.get(f"{CLOB_API}/markets/{condition_id}", timeout=8)
        if r.status_code != 200:
            return None, "CLOB error"
        tokens = r.json().get("tokens", [])
        for t in tokens:
            if str(t.get("outcome", "")).upper() == "NO":
                return float(t["price"]), "CLOB live"
        if len(tokens) >= 2:
            return float(tokens[1]["price"]), "CLOB live (idx 1)"
    except Exception as e:
        return None, f"error: {e}"
    return None, "no encontrado"


# ── Noticias RSS ─────────────────────────────────────────────────────────────

def es_relevante(texto):
    return any(kw in texto.lower() for kw in KEYWORDS_IRAN)

def calcular_impacto(texto):
    """Detecta qué posiciones afecta la noticia."""
    t = texto.lower()
    impactos = []
    if any(kw in t for kw in IMPACTO_CEASEFIRE_APR15):
        impactos.append("NO ceasefire Apr15")
    if any(kw in t for kw in IMPACTO_CONFLICT_JUN30):
        impactos.append("NO conflict Jun30")
    return impactos if impactos else ["—"]

def parsear_fecha(raw):
    """Convierte pubDate RSS a objeto datetime para ordenar. Devuelve None si falla."""
    if not raw:
        return None
    # Formatos comunes en RSS
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None

def parsear_feed(feed_info, timeout=10):
    noticias = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; InversionBot/1.0)"}
        r = requests.get(feed_info["url"], headers=headers, timeout=timeout)
        if r.status_code != 200:
            return noticias
        # Google News devuelve Atom a veces; usar lxml-style con namespaces ignorados
        content = r.content.replace(b' xmlns="', b' xmlnsx="')  # evitar conflicto ns
        root = ET.fromstring(content)
        items = root.findall(".//item")
        for item in items:
            titulo_item = item.findtext("title", "").strip()
            desc        = item.findtext("description", "").strip()
            link        = item.findtext("link", "").strip()
            pub_date    = item.findtext("pubDate", "").strip()
            texto_completo = f"{titulo_item} {desc}"
            if not es_relevante(texto_completo):
                continue
            impactos = calcular_impacto(texto_completo)
            noticias.append({
                "fuente":   feed_info["nombre"],
                "nivel":    feed_info["nivel"],
                "idioma":   feed_info.get("idioma", "en"),
                "titulo":   titulo_item,
                "link":     link,
                "fecha_raw": pub_date,
                "fecha_dt": parsear_fecha(pub_date),
                "impacto":  impactos,
            })
    except Exception:
        pass
    return noticias

def obtener_noticias(max_total=10):
    """Recoge noticias de todos los feeds, deduplica por título y ordena por fecha."""
    todas = []
    vistos = set()
    for feed in RSS_FEEDS:
        for n in parsear_feed(feed):
            clave = n["titulo"][:60].lower()
            if clave not in vistos:
                vistos.add(clave)
                todas.append(n)

    # Ordenar: primero las que tienen fecha parseada (más recientes primero),
    # luego las sin fecha al final
    con_fecha    = [n for n in todas if n["fecha_dt"] is not None]
    sin_fecha    = [n for n in todas if n["fecha_dt"] is None]
    # Normalizar: convertir todas a naive UTC para poder comparar
    from datetime import timezone
    def a_naive(dt):
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    con_fecha.sort(key=lambda x: a_naive(x["fecha_dt"]), reverse=True)
    return (con_fecha + sin_fecha)[:max_total]


# ── Alertas de riesgo ────────────────────────────────────────────────────────

def calcular_alertas(portfolio):
    alertas = []
    perfil = portfolio["perfil"]
    posiciones = portfolio["posiciones_polymarket"]

    # Liquidez crítica
    if perfil["cash_disponible"] < 1.0:
        alertas.append({
            "nivel": "CRITICO",
            "tipo": "LIQUIDEZ",
            "msg": f"Cash disponible: ${perfil['cash_disponible']:.2f} — Sin capacidad de nuevas posiciones ni emergencias"
        })

    # Concentración de capital
    valor_total = sum(p["valor_actual"] for p in posiciones)
    for p in posiciones:
        pct = (p["valor_actual"] / valor_total) * 100
        if pct > 60:
            alertas.append({
                "nivel": "ALTO",
                "tipo": "CONCENTRACION",
                "msg": f"{p['mercado'][:40]}... representa {pct:.0f}% del portfolio"
            })

    # Deadline crítico
    hoy = datetime.today().date()
    for p in posiciones:
        venc = datetime.strptime(p["fecha_resolucion"], "%Y-%m-%d").date()
        dias = (venc - hoy).days
        if dias <= 20:
            alertas.append({
                "nivel": "ALTO",
                "tipo": "DEADLINE",
                "msg": f"{p['mercado'][:40]}... vence en {dias} días ({p['fecha_resolucion']})"
            })

    # Insider trading
    for p in posiciones:
        for r in p.get("riesgos", []):
            if "insider" in r.lower() or "nothingeverfrickin" in r.lower():
                alertas.append({
                    "nivel": "ALTO",
                    "tipo": "INSIDER",
                    "msg": f"[{p['mercado'][:35]}...] {r[:80]}"
                })
                break

    # Sin condition_id — precios estimados
    sin_live = [p for p in posiciones if not p.get("condition_id")]
    if sin_live:
        alertas.append({
            "nivel": "INFO",
            "tipo": "PRECIO",
            "msg": f"{len(sin_live)} posiciones con precio ESTIMADO (configurar condition_id para precio live)"
        })

    return alertas


# ═══════════════════════════════════════════════════════════════════════════
# HISTORIAL DE TRADES — REGISTRO Y APRENDIZAJE
# ═══════════════════════════════════════════════════════════════════════════

def cargar_historial():
    if not HISTORIAL_FILE.exists():
        return {"trades": [], "estadisticas": {}}
    with open(HISTORIAL_FILE, encoding="utf-8") as f:
        return json.load(f)

def guardar_historial(h):
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

def _bucket(prob):
    if prob is None:
        return None
    if prob < 0.30:
        return "menos_30pct"
    if prob < 0.50:
        return "30_50pct"
    if prob < 0.70:
        return "50_70pct"
    return "mas_70pct"

def _recalcular_estadisticas(h):
    """Recalcula todas las estadísticas globales desde los trades."""
    trades    = h["trades"]
    resueltos = [t for t in trades if t["estado"] == "resuelto"]
    ganados   = [t for t in resueltos if t["resultado"] == "ganado"]
    perdidos  = [t for t in resueltos if t["resultado"] == "perdido"]

    # Métricas básicas
    win_rate   = len(ganados) / len(resueltos) * 100 if resueltos else None
    pnl_total  = sum(t["pnl_absoluto"] for t in resueltos if t["pnl_absoluto"] is not None)

    # Edge estimado vs real
    con_edge_est  = [t for t in resueltos if t["edge_estimado_pp"] is not None]
    con_edge_real = [t for t in resueltos if t["edge_real_pp"] is not None]
    edge_est_prom  = sum(t["edge_estimado_pp"] for t in con_edge_est)  / len(con_edge_est)  if con_edge_est  else None
    edge_real_prom = sum(t["edge_real_pp"]      for t in con_edge_real) / len(con_edge_real) if con_edge_real else None
    error_medio    = sum(t["error_estimacion_pp"] for t in resueltos if t["error_estimacion_pp"] is not None)
    errores        = [t for t in resueltos if t["error_estimacion_pp"] is not None]
    error_medio    = sum(t["error_estimacion_pp"] for t in errores) / len(errores) if errores else None

    # Sesgo sistemático
    sesgo = None
    if error_medio is not None:
        if error_medio > 5:
            sesgo = f"Subestimas el edge sistematicamente (+{error_medio:.1f}pp de media)"
        elif error_medio < -5:
            sesgo = f"Sobreestimas el edge sistematicamente ({error_medio:.1f}pp de media)"
        else:
            sesgo = f"Sin sesgo sistematico significativo (error medio {error_medio:+.1f}pp)"

    # Brier score (calibración probabilística)
    con_brier = [t for t in resueltos if t["brier_score"] is not None]
    brier_prom = sum(t["brier_score"] for t in con_brier) / len(con_brier) if con_brier else None

    # Calibración por bucket
    buckets = {
        "menos_30pct": {"trades": 0, "ganados": 0, "win_rate_real": None},
        "30_50pct":    {"trades": 0, "ganados": 0, "win_rate_real": None},
        "50_70pct":    {"trades": 0, "ganados": 0, "win_rate_real": None},
        "mas_70pct":   {"trades": 0, "ganados": 0, "win_rate_real": None},
    }
    for t in resueltos:
        b = t.get("calibracion_bucket")
        if b and b in buckets:
            buckets[b]["trades"] += 1
            if t["resultado"] == "ganado":
                buckets[b]["ganados"] += 1
    for b, datos in buckets.items():
        if datos["trades"] > 0:
            datos["win_rate_real"] = round(datos["ganados"] / datos["trades"] * 100, 1)

    # Errores frecuentes (riesgos que se materializaron pero no se incorporaron al edge)
    riesgos_count = {}
    for t in resueltos:
        if t["resultado"] == "perdido":
            for r in t.get("riesgos_materializados", []):
                riesgos_count[r] = riesgos_count.get(r, 0) + 1
    errores_frecuentes = sorted(riesgos_count.items(), key=lambda x: x[1], reverse=True)[:3]

    h["estadisticas"] = {
        "total_trades":              len(trades),
        "abiertos":                  len([t for t in trades if t["estado"] == "abierto"]),
        "resueltos":                 len(resueltos),
        "ganados":                   len(ganados),
        "perdidos":                  len(perdidos),
        "win_rate_pct":              round(win_rate, 1) if win_rate is not None else None,
        "pnl_total_usd":             round(pnl_total, 2),
        "edge_estimado_promedio_pp": round(edge_est_prom, 2) if edge_est_prom is not None else None,
        "edge_real_promedio_pp":     round(edge_real_prom, 2) if edge_real_prom is not None else None,
        "error_medio_estimacion_pp": round(error_medio, 2) if error_medio is not None else None,
        "brier_score_promedio":      round(brier_prom, 4) if brier_prom is not None else None,
        "sesgo_sistematico":         sesgo,
        "calibracion_por_bucket":    buckets,
        "errores_frecuentes":        [{"riesgo": r, "veces": n} for r, n in errores_frecuentes],
        "ultima_actualizacion":      datetime.now().strftime("%Y-%m-%d"),
    }
    return h


def registrar_trade(mercado, direccion, precio_entrada, shares, capital,
                    fecha_entrada=None, prob_propia=None, edge_estimado=None,
                    fuentes=None, riesgos=None, condition_id=None,
                    fecha_resolucion=None, notas=""):
    """
    Registra un nuevo trade en historial_trades.json.

    Parámetros:
        mercado          : nombre del mercado (str)
        direccion        : "YES" o "NO"
        precio_entrada   : precio promedio de entrada (float, 0-1)
        shares           : número de shares compradas (float)
        capital          : capital invertido en USD (float)
        fecha_entrada    : "YYYY-MM-DD" (default: hoy)
        prob_propia      : probabilidad propia estimada (float 0-1, o None)
        edge_estimado    : edge en pp (float, o None)
        fuentes          : lista de strings ["Reuters [B]", "IEA [A]", ...]
        riesgos          : lista de strings con riesgos identificados
        condition_id     : ID del mercado en Polymarket (str, o None)
        fecha_resolucion : "YYYY-MM-DD"
        notas            : texto libre con contexto del trade

    Ejemplo:
        registrar_trade(
            mercado="Will X win election?",
            direccion="NO",
            precio_entrada=0.35,
            shares=100,
            capital=35.0,
            prob_propia=0.25,
            edge_estimado=10.0,
            fuentes=["Reuters [B]", "Parlamento oficial [A]"],
            riesgos=["Trump effect", "Volumen bajo"],
            fecha_resolucion="2026-05-15",
            notas="Encuestas dan 25% de probabilidad real vs 35% del mercado"
        )
    """
    h    = cargar_historial()
    hoy  = datetime.now().strftime("%Y-%m-%d")
    ids  = [t["id"] for t in h["trades"]]
    nuevo_id = max(ids) + 1 if ids else 1

    # Precio del lado apostado (para calcular edge desde la dirección correcta)
    prob_mercado = (1 - precio_entrada) if direccion == "NO" else precio_entrada

    trade = {
        "id":                    nuevo_id,
        "fecha_entrada":         fecha_entrada or hoy,
        "mercado":               mercado,
        "direccion":             direccion,
        "precio_entrada_avg":    precio_entrada,
        "shares":                shares,
        "capital_invertido":     capital,
        "prob_mercado_entrada":  round(prob_mercado, 4),
        "prob_propia_estimada":  prob_propia,
        "edge_estimado_pp":      edge_estimado,
        "calibracion_bucket":    _bucket(prob_propia),
        "fuentes_usadas":        fuentes or [],
        "riesgos_identificados": riesgos or [],
        "condition_id":          condition_id,
        "fecha_resolucion_esperada": fecha_resolucion,
        "estado":                "abierto",
        "resultado":             None,
        "precio_salida":         None,
        "precio_mercado_salida": None,
        "pnl_absoluto":          None,
        "pnl_pct":               None,
        "edge_real_pp":          None,
        "error_estimacion_pp":   None,
        "brier_score":           None,
        "riesgos_materializados":[],
        "aprendizaje":           "",
        "notas":                 notas,
    }

    h["trades"].append(trade)
    h = _recalcular_estadisticas(h)
    guardar_historial(h)
    print(f"  [+] Trade #{nuevo_id} registrado: {mercado[:50]} | {direccion} @ {precio_entrada}")
    return nuevo_id


def resolver_trade(trade_id, resultado, precio_salida,
                   precio_mercado_salida=None,
                   riesgos_materializados=None,
                   aprendizaje=""):
    """
    Resuelve un trade y calcula edge real, error de estimación y Brier score.

    Parámetros:
        trade_id                 : ID del trade a resolver
        resultado                : "ganado" | "perdido" | "nulo"
        precio_salida            : precio al que se cerró la posición (float 0-1)
        precio_mercado_salida    : precio del mercado en el momento de salida (float, opcional)
        riesgos_materializados   : lista de strings con riesgos que se cumplieron
        aprendizaje              : texto libre — qué aprendiste de este trade

    Ejemplo:
        resolver_trade(
            trade_id=1,
            resultado="ganado",
            precio_salida=0.98,
            precio_mercado_salida=0.98,
            riesgos_materializados=[],
            aprendizaje="El insider tenia razon pero el conflicto siguio. El mercado sobrevaloro el ceasefire."
        )
    """
    h      = cargar_historial()
    trades = h["trades"]
    trade  = next((t for t in trades if t["id"] == trade_id), None)

    if trade is None:
        print(f"  [!] Trade #{trade_id} no encontrado.")
        return

    if trade["estado"] == "resuelto":
        print(f"  [!] Trade #{trade_id} ya está resuelto.")
        return

    hoy           = datetime.now().strftime("%Y-%m-%d")
    shares        = trade["shares"]
    entrada       = trade["precio_entrada_avg"]
    direccion     = trade["direccion"]
    prob_mercado  = trade["prob_mercado_entrada"]  # prob del lado apostado al entrar
    prob_propia   = trade["prob_propia_estimada"]
    edge_estimado = trade["edge_estimado_pp"]

    # PnL
    if direccion == "NO":
        # Apostamos NO: ganamos si el precio NO sube (precio YES baja)
        # precio_salida = precio del outcome NO al salir
        pnl_abs = (precio_salida - entrada) * shares
    else:
        pnl_abs = (precio_salida - entrada) * shares
    pnl_pct = (pnl_abs / trade["capital_invertido"]) * 100 if trade["capital_invertido"] else 0

    # Resultado binario: 1 = ganado, 0 = perdido
    resultado_bin = 1 if resultado == "ganado" else 0

    # Edge real = (resultado_binario - prob_mercado_entrada) * 100
    edge_real = (resultado_bin - prob_mercado) * 100

    # Error de estimación
    error = (edge_real - edge_estimado) if edge_estimado is not None else None

    # Brier score = (resultado - prob_propia)^2  — mide calibración
    brier = (resultado_bin - prob_propia) ** 2 if prob_propia is not None else None

    # Actualizar trade
    trade.update({
        "estado":                 "resuelto",
        "resultado":              resultado,
        "precio_salida":          precio_salida,
        "precio_mercado_salida":  precio_mercado_salida,
        "fecha_resolucion_real":  hoy,
        "pnl_absoluto":           round(pnl_abs, 2),
        "pnl_pct":                round(pnl_pct, 2),
        "edge_real_pp":           round(edge_real, 2),
        "error_estimacion_pp":    round(error, 2) if error is not None else None,
        "brier_score":            round(brier, 4) if brier is not None else None,
        "riesgos_materializados": riesgos_materializados or [],
        "aprendizaje":            aprendizaje,
    })

    h = _recalcular_estadisticas(h)
    guardar_historial(h)

    print(f"  [✓] Trade #{trade_id} resuelto: {resultado.upper()}")
    print(f"      PnL: {'+' if pnl_abs >= 0 else ''}{pnl_abs:.2f} USD ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)")
    print(f"      Edge real: {edge_real:+.1f}pp  |  Brier score: {brier:.4f}" if brier else
          f"      Edge real: {edge_real:+.1f}pp")
    if error is not None:
        print(f"      Error estimacion: {error:+.1f}pp ({'subestimaste' if error > 0 else 'sobreestimaste'} el edge)")


def actualizar_trade(trade_id, **kwargs):
    """
    Actualiza campos de un trade abierto (prob_propia, edge_estimado, fuentes, notas…).

    Ejemplo:
        actualizar_trade(1,
            prob_propia_estimada=0.82,
            edge_estimado_pp=15.0,
            fuentes_usadas=["Al Jazeera [B]", "IAEA [A]"],
            notas="Actualizado tras rechazo plan Trump 25 marzo"
        )
    """
    h = cargar_historial()
    trade = next((t for t in h["trades"] if t["id"] == trade_id), None)
    if trade is None:
        print(f"  [!] Trade #{trade_id} no encontrado.")
        return
    for k, v in kwargs.items():
        if k in trade:
            trade[k] = v
    # Recalcular bucket si cambió prob_propia
    if "prob_propia_estimada" in kwargs:
        trade["calibracion_bucket"] = _bucket(kwargs["prob_propia_estimada"])
    h = _recalcular_estadisticas(h)
    guardar_historial(h)
    print(f"  [~] Trade #{trade_id} actualizado: {', '.join(kwargs.keys())}")


# ── Sección historial para main() ────────────────────────────────────────────

def _barra_calibracion(win_rate_real, prob_esperada_centro, ancho=20):
    """Mini barra visual de calibración."""
    if win_rate_real is None:
        return "  (sin datos)"
    lleno   = int(win_rate_real / 100 * ancho)
    esperado = int(prob_esperada_centro * ancho)
    barra   = list("─" * ancho)
    for i in range(lleno):
        barra[i] = "█"
    if 0 <= esperado < ancho:
        barra[esperado] = "◆"   # marca donde debería estar
    return "".join(barra) + f"  {win_rate_real:.0f}% real  (esperado ≈{prob_esperada_centro*100:.0f}%)"

def mostrar_historial():
    """Muestra el historial de trades y las métricas de aprendizaje."""
    h      = cargar_historial()
    trades = h.get("trades", [])
    stats  = h.get("estadisticas", {})

    titulo("HISTORIAL DE TRADES & APRENDIZAJE")

    if not trades:
        print("  Sin trades registrados todavia.")
        print("  Usa registrar_trade() para añadir tu primera operacion.")
        return

    # ── Trades abiertos ───────────────────────────────────────────────────────
    abiertos = [t for t in trades if t["estado"] == "abierto"]
    if abiertos:
        print(f"  POSICIONES ABIERTAS ({len(abiertos)})\n")
        for t in abiertos:
            dias_str = ""
            if t.get("fecha_resolucion_esperada"):
                try:
                    dias = (datetime.strptime(t["fecha_resolucion_esperada"], "%Y-%m-%d").date()
                            - datetime.today().date()).days
                    dias_str = f"  ({dias}d)"
                except Exception:
                    pass
            edge_str = f"  Edge est: {t['edge_estimado_pp']:+.1f}pp" if t.get("edge_estimado_pp") is not None else "  Edge est: N/D"
            prob_str = f"  Prob propia: {t['prob_propia_estimada']:.0%}" if t.get("prob_propia_estimada") is not None else "  Prob propia: N/D"
            print(f"  #{t['id']:02d} | {t['mercado'][:48]}")
            print(f"       {t['direccion']} @ {t['precio_entrada_avg']:.3f}  |  ${t['capital_invertido']:.2f}  |  Vence: {t.get('fecha_resolucion_esperada','?')}{dias_str}")
            print(f"      {prob_str}{edge_str}")
            if t.get("fuentes_usadas"):
                print(f"       Fuentes: {', '.join(t['fuentes_usadas'][:3])}")
            if not t.get("prob_propia_estimada"):
                print(f"       [ i ] Sin prob propia — usar actualizar_trade({t['id']}, prob_propia_estimada=X, edge_estimado_pp=Y)")
            print()

    # ── Trades resueltos ──────────────────────────────────────────────────────
    resueltos = [t for t in trades if t["estado"] == "resuelto"]
    if resueltos:
        sep()
        print(f"\n  TRADES RESUELTOS ({len(resueltos)})\n")
        for t in sorted(resueltos, key=lambda x: x.get("fecha_resolucion_real", ""), reverse=True):
            icono = "[G]" if t["resultado"] == "ganado" else "[P]"
            pnl   = t.get("pnl_absoluto", 0) or 0
            er    = t.get("edge_real_pp")
            ee    = t.get("edge_estimado_pp")
            err   = t.get("error_estimacion_pp")
            bs    = t.get("brier_score")

            print(f"  {icono} #{t['id']:02d} | {t['mercado'][:50]}")
            print(f"       {t['direccion']} @ {t['precio_entrada_avg']:.3f} → {t.get('precio_salida','?')}  |  PnL: {'+' if pnl >= 0 else ''}{pnl:.2f} USD")
            if er is not None:
                print(f"       Edge real: {er:+.1f}pp  |  Edge estimado: {f'{ee:+.1f}pp' if ee is not None else 'N/D'}  |  Error: {f'{err:+.1f}pp' if err is not None else 'N/D'}")
            if bs is not None:
                calif = "excelente" if bs < 0.05 else ("buena" if bs < 0.15 else ("regular" if bs < 0.25 else "mala"))
                print(f"       Brier score: {bs:.4f} ({calif} calibracion)")
            if t.get("aprendizaje"):
                print(f"       Aprendizaje: {t['aprendizaje'][:80]}")
            if t.get("riesgos_materializados"):
                print(f"       Riesgos materializados: {', '.join(t['riesgos_materializados'][:2])}")
            print()

    # ── Estadísticas globales ─────────────────────────────────────────────────
    if stats.get("resueltos", 0) == 0:
        sep()
        print("\n  ESTADISTICAS")
        print(f"  Sin trades resueltos todavia — las metricas apareceran tras la primera resolucion.")
        print(f"  Trades registrados: {stats.get('total_trades', 0)}  |  Abiertos: {stats.get('abiertos', 0)}")
        return

    sep()
    print("\n  ESTADISTICAS GLOBALES\n")
    wr = stats.get("win_rate_pct")
    print(f"  Win rate     : {wr:.1f}%  ({stats['ganados']}G / {stats['perdidos']}P de {stats['resueltos']} resueltos)" if wr else "  Win rate: N/D")
    pnl_t = stats.get("pnl_total_usd", 0)
    print(f"  PnL total    : {'+' if pnl_t >= 0 else ''}{pnl_t:.2f} USD")
    ee_p  = stats.get("edge_estimado_promedio_pp")
    er_p  = stats.get("edge_real_promedio_pp")
    if ee_p is not None:
        print(f"  Edge estimado promedio : {ee_p:+.1f}pp")
    if er_p is not None:
        print(f"  Edge real promedio     : {er_p:+.1f}pp")
    err_m = stats.get("error_medio_estimacion_pp")
    if err_m is not None:
        print(f"  Error medio estimacion : {err_m:+.1f}pp")
    bs_p  = stats.get("brier_score_promedio")
    if bs_p is not None:
        calif = "excelente" if bs_p < 0.05 else ("buena" if bs_p < 0.15 else ("regular" if bs_p < 0.25 else "mala"))
        print(f"  Brier score promedio   : {bs_p:.4f} ({calif} calibracion de probabilidades)")

    # Sesgo sistemático
    sesgo = stats.get("sesgo_sistematico")
    if sesgo:
        print(f"\n  SESGO SISTEMATICO: {sesgo}")

    # Calibración por bucket
    buckets = stats.get("calibracion_por_bucket", {})
    centros = {"menos_30pct": 0.20, "30_50pct": 0.40, "50_70pct": 0.60, "mas_70pct": 0.80}
    etiq    = {"menos_30pct": "<30%", "30_50pct": "30-50%", "50_70pct": "50-70%", "mas_70pct": ">70%"}
    tiene_datos = any(buckets.get(b, {}).get("trades", 0) > 0 for b in buckets)
    if tiene_datos:
        print("\n  CALIBRACION POR BUCKET (◆ = win rate esperado, █ = win rate real):\n")
        for b, centro in centros.items():
            datos = buckets.get(b, {})
            n     = datos.get("trades", 0)
            if n == 0:
                print(f"  {etiq[b]:8s} : sin datos")
                continue
            barra = _barra_calibracion(datos.get("win_rate_real"), centro)
            print(f"  {etiq[b]:8s} : {barra}  (n={n})")

    # Errores frecuentes
    errores = stats.get("errores_frecuentes", [])
    if errores:
        print("\n  ERRORES FRECUENTES (riesgos que se materializaron en trades perdidos):\n")
        for e in errores:
            print(f"    - [{e['veces']}x] {e['riesgo']}")

    print()


# ── Oportunidades con edge ────────────────────────────────────────────────────

def _precio_valido(prices):
    """
    Extrae p_yes de outcomePrices solo si el mercado está abierto (precio entre 0.03 y 0.97).
    outcomePrices puede ser lista Python o JSON string — maneja ambos casos.
    """
    import json as _json
    if not prices:
        return None
    try:
        # Gamma API a veces devuelve JSON string en vez de lista
        if isinstance(prices, str):
            prices = _json.loads(prices)
        p = float(str(prices[0]).strip('"\''))
        return p if 0.03 <= p <= 0.97 else None
    except Exception:
        return None

def top_oportunidades(n=3, vol_min=200_000):
    """
    Devuelve los N mercados activos con precio válido y mayor volumen desde Gamma API.
    Filtra en Python los mercados ya resueltos (prices en 0/1 o vacíos).
    Son candidatos para analizar si existe edge — no garantia de edge.
    """
    try:
        candidatos = []
        for offset in range(0, 500, 100):
            params = {"limit": 100, "active": "true",
                      "order": "volumeNum", "ascending": "false", "offset": offset}
            r = requests.get(f"{GAMMA_API}/markets", params=params, timeout=12)
            if r.status_code != 200:
                break
            markets = r.json()
            if not markets:
                break
            ultimo_vol = 0
            for m in markets:
                try:
                    vol = float(m.get("volumeNum") or m.get("volume") or 0)
                except Exception:
                    vol = 0
                ultimo_vol = vol
                if vol < vol_min:
                    continue
                if m.get("closed"):
                    continue
                prices = m.get("outcomePrices", [])
                p_yes = _precio_valido(prices)
                if p_yes is None:
                    continue
                candidatos.append({
                    "mercado": m.get("question", "")[:65],
                    "p_yes": p_yes,
                    "p_no": round(1 - p_yes, 4),
                    "vol_usd": vol,
                    "slug": m.get("slug", ""),
                    "extremo": p_yes <= 0.25 or p_yes >= 0.75,
                })
                if len(candidatos) >= n * 5:
                    break
            if ultimo_vol < vol_min or len(candidatos) >= n * 5:
                break

        # Priorizar mercados con precios extremos (más probable que haya edge)
        extremos = [c for c in candidatos if c["extremo"]]
        normales = [c for c in candidatos if not c["extremo"]]
        return (extremos + normales)[:n]
    except Exception:
        return []




# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Analisis de portfolio con historial de trades")
    parser.add_argument("--registrar", action="store_true", help="Registrar un nuevo trade interactivamente")
    parser.add_argument("--resolver",  type=int, metavar="ID",   help="Resolver el trade con este ID")
    parser.add_argument("--actualizar",type=int, metavar="ID",   help="Actualizar campos de un trade abierto")
    parser.add_argument("--historial", action="store_true",      help="Mostrar solo el historial y salir")
    parser.add_argument("--rapido",    action="store_true",      help="Solo portfolio + estres + sesgos (sin RSS ni Gamma API)")
    args = parser.parse_args()

    # Modo solo historial
    if args.historial:
        mostrar_historial()
        return

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    portfolio = cargar_portfolio()
    perfil = portfolio["perfil"]
    posiciones = portfolio["posiciones_polymarket"]
    watchlist = portfolio["equity_watchlist"]
    macro = portfolio["contexto_macro"]

    titulo(f"SISTEMA DE ANALISIS — {ahora}")
    print(f"  Inversor : {perfil['nombre']}  |  Broker: {perfil['broker_principal']}")
    print(f"  Capital  : ${perfil['capital_total_usdc']:.2f} USDC  |  Cash: ${perfil['cash_disponible']:.2f}")
    print()

    # ── Posiciones Polymarket ─────────────────────────────────────────────────
    titulo("POLYMARKET — POSICIONES ABIERTAS")

    SLUG_DIRECTO = {
        "Iran x Israel/US conflict ends by June 30?":
            "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725",
    }

    def _precio_por_slug(slug, outcome="no"):
        """Obtiene precio YES o NO de un mercado via slug Gamma API."""
        try:
            r = requests.get(
                f"{GAMMA_API}/markets",
                params={"slug": slug},
                timeout=8
            )
            if r.status_code != 200:
                return None, f"Gamma error {r.status_code}"
            data = r.json()
            if not data:
                return None, "sin datos"
            m = data[0]
            precios = m.get("outcomePrices", [])
            if isinstance(precios, str):
                import json as _j
                precios = _j.loads(precios)
            idx = 1 if outcome == "no" else 0
            precio = float(str(precios[idx]).strip('"\''))
            return precio, f"Gamma live ({outcome.upper()} directo)"
        except Exception as e:
            return None, f"error: {e}"

    total_costo = total_valor = total_pnl = 0.0

    for p in posiciones:
        cid = p.get("condition_id")
        precio_live, fuente = precio_polymarket(cid)
        if precio_live is None:
            slug_alt = SLUG_DIRECTO.get(p["mercado"])
            if slug_alt:
                outcome = p.get("direccion", "no").lower()
                precio_live, fuente = _precio_por_slug(slug_alt, outcome)
            if precio_live is None:
                precio_live = p["precio_entrada_avg"]
                fuente = "estimado (sin API)"

        valor = p["shares"] * precio_live
        costo = p["shares"] * p["precio_entrada_avg"]
        pnl_abs = valor - costo
        pnl_pct = (pnl_abs / costo) * 100 if costo else 0
        dias = (datetime.strptime(p["fecha_resolucion"], "%Y-%m-%d").date() - datetime.today().date()).days

        total_costo += costo
        total_valor += valor
        total_pnl   += pnl_abs

        sep()
        print(f"  Mercado  : {p['mercado']}")
        print(f"  Posicion : {p['direccion']}  |  Shares: {p['shares']:.1f}  |  Precio entrada: {p['precio_entrada_avg']:.3f}")
        print(f"  Precio actual: {precio_live:.4f}  [{fuente}]")
        print(f"  Costo base   : ${costo:.2f}  |  Valor actual: ${valor:.2f}")
        print(f"  P/L          : {s(pnl_abs)}${pnl_abs:.2f}  ({s(pnl_pct)}{pnl_pct:.1f}%)")
        print(f"  Vence        : {p['fecha_resolucion']}  ({dias} dias restantes)")
        if p.get("ratio_potencial"):
            print(f"  Ratio potencial NO: {p['ratio_potencial']}x")

    sep()
    total_pnl_pct = (total_pnl / total_costo) * 100 if total_costo else 0
    print(f"\n  TOTAL PORTFOLIO")
    print(f"  Costo base  : ${total_costo:.2f}")
    print(f"  Valor actual: ${total_valor:.2f}")
    print(f"  P/L total   : {s(total_pnl)}${total_pnl:.2f}  ({s(total_pnl_pct)}{total_pnl_pct:.1f}%)")
    print(f"  Capital USDC: ${perfil['capital_total_usdc']:.2f}")

    # ── Índice de estrés ──────────────────────────────────────────────────────
    print()
    titulo("INDICE DE ESTRES DEL DIA")
    if _HERRAMIENTAS_OK:
        historial_data = cargar_historial()
        estres = calcular_indice_estres(portfolio, historial_data, verbose=False)
        nivel  = estres["nivel"]
        puntos = estres["puntuacion"]
        barra_lleno = int(puntos / 100 * 30)
        barra = "█" * barra_lleno + "░" * (30 - barra_lleno)
        colores_txt = {"VERDE":    "VERDE — operar con normalidad",
                       "AMARILLO": "AMARILLO — operar con cautela",
                       "NARANJA":  "NARANJA — no abrir nuevas posiciones",
                       "ROJO":     "ROJO — cerrar posiciones y descansar"}
        print(f"  [{barra}] {puntos}/100  {colores_txt.get(nivel, nivel)}\n")
        if estres.get("factores"):
            print("  Factores activos:")
            for f in estres["factores"]:
                pts = f["puntos"]
                print(f"    {pts:+3d}  {f['factor']}")
        if estres.get("accion"):
            print(f"\n  Recomendacion: {estres['accion']}")
    else:
        print("  [!] herramientas_avanzadas.py no disponible.")

    # ── Sesgos activos ────────────────────────────────────────────────────────
    print()
    titulo("ALERTAS DE SESGOS ACTIVOS")
    if _SESGOS_OK:
        historial_data = historial_data if _HERRAMIENTAS_OK else cargar_historial()
        alg_sesgo = False
        for p in posiciones:
            alertas_sesgo = detectar_sesgos_posicion(p, historial_data)
            if alertas_sesgo:
                alg_sesgo = True
                mostrar_sesgos_activos(alertas_sesgo, p["mercado"][:45])
        if not alg_sesgo:
            print("  Sin sesgos activos detectados en posiciones abiertas. [OK]")
    else:
        print("  [!] sesgos_psicologicos.py no disponible.")

    # ── Alertas de riesgo ─────────────────────────────────────────────────────
    print()
    titulo("ALERTAS DE RIESGO")
    alertas = calcular_alertas(portfolio)
    if not alertas:
        print("  Sin alertas activas.")
    else:
        iconos = {"CRITICO": "[!!!]", "ALTO": "[ ! ]", "INFO": "[ i ]"}
        for a in alertas:
            icono = iconos.get(a["nivel"], "[ ? ]")
            print(f"  {icono} {a['nivel']:8s} | {a['tipo']:12s} | {a['msg']}")

    # ── Macro ─────────────────────────────────────────────────────────────────
    print()
    titulo("CONTEXTO MACRO")
    brent   = macro.get('brent_usd', 0)
    brent_c = macro.get('brent_cambio_pct')
    wti     = macro.get('wti_usd', 0)
    wti_c   = macro.get('wti_cambio_pct')
    brent_str = f"${brent:.2f}  ({s(brent_c)}{brent_c}%)" if brent_c is not None else f"${brent:.2f}"
    wti_str   = f"${wti:.2f}   ({s(wti_c)}{wti_c}%)"     if wti_c   is not None else f"${wti:.2f}" if wti else "N/D"
    print(f"  Brent    : {brent_str}")
    print(f"  WTI      : {wti_str}")
    print(f"  Conflicto Iran: dia {macro.get('conflicto_iran_dia', '?')}")
    rec = macro.get('probabilidad_recesion_2026_polymarket_pct')
    if rec is not None:
        print(f"  Recesion 2026 (Polymarket): {rec}%")
    print()
    print("  Eventos criticos proximos:")
    for ev in macro["eventos_criticos"][:4]:
        print(f"    - {ev}")

    # ── Equity Watchlist ──────────────────────────────────────────────────────
    print()
    titulo("EQUITY WATCHLIST")
    for eq in watchlist:
        print(f"  Ticker   : {eq['ticker']} ({eq['nombre']})")
        try:
            t = yf.Ticker(eq["ticker"])
            info = t.info
            precio = info.get("currentPrice") or info.get("regularMarketPrice")
        except Exception:
            precio = None

        if precio:
            en_zona = eq["zona_entrada_min"] <= precio <= eq["zona_entrada_max"]
            bajo_consenso = precio < eq["consenso_analistas"]
            estado = "ENTRAR AHORA" if en_zona else ("WAIT — precio elevado" if precio > eq["zona_entrada_max"] else "WAIT — precio bajo zona")
            print(f"  Precio   : ${precio:.2f}  |  Estado: {estado}")
            print(f"  Zona entrada: ${eq['zona_entrada_min']}-${eq['zona_entrada_max']}  |  Consenso analistas: ${eq['consenso_analistas']}")
            print(f"  Beta     : {eq['beta']}  |  Earnings: {eq['earnings_date']}")
            if bajo_consenso:
                print(f"  [!] Precio bajo consenso analistas — posible oportunidad")
        else:
            print(f"  Precio   : no disponible")
            print(f"  Zona entrada: ${eq['zona_entrada_min']}-${eq['zona_entrada_max']}  |  Estado: {eq['estado']}")

    # ── Noticias ──────────────────────────────────────────────────────────────
    if not args.rapido:
        print()
        fuentes_str = "Al Jazeera · Reuters · AP · EFE · AFP/Google"
        titulo(f"NOTICIAS RELEVANTES — RSS TIEMPO REAL  [{fuentes_str}]")
        print("  Consultando feeds...", end=" ", flush=True)
        noticias = obtener_noticias(max_total=10)
        print(f"{len(noticias)} noticias relevantes encontradas\n")

        if noticias:
            for i, n in enumerate(noticias, 1):
                etiqueta_nivel = f"[{n['nivel']}]"
                etiqueta_idioma = "[ES]" if n["idioma"] == "es" else "[EN]"
                fecha_fmt = ""
                if n["fecha_dt"]:
                    fecha_fmt = n["fecha_dt"].strftime("%d %b %Y %H:%M UTC")
                elif n["fecha_raw"]:
                    fecha_fmt = n["fecha_raw"][:30]
                impacto_str = " | ".join(n["impacto"])

                print(f"  [{i:02d}] {n['fuente']:18s} {etiqueta_nivel} {etiqueta_idioma}")
                print(f"        {n['titulo']}")
                if fecha_fmt:
                    print(f"        Fecha   : {fecha_fmt}")
                print(f"        Impacto : {impacto_str}")
                if n.get("link"):
                    print(f"        URL     : {n['link'][:80]}")
                print()
        else:
            print("  Sin noticias relevantes en este momento.")
            print("  (Feeds pueden estar temporalmente no disponibles)")

    # ── Oportunidades con edge ────────────────────────────────────────────────
    if not args.rapido:
        print()
        titulo("OPORTUNIDADES CON EDGE — TOP 3 (requieren analisis propio)")
        print("  Consultando Gamma API...", end=" ", flush=True)
        ops = top_oportunidades(n=3)
        print(f"{len(ops)} candidatos encontrados\n")
        if ops:
            for i, op in enumerate(ops, 1):
                p_yes = op["p_yes"]
                p_no  = op["p_no"]
                sesgo_txt = ""
                if p_yes <= 0.25:
                    sesgo_txt = "  [cotiza BAJO — investigar YES]"
                elif p_yes >= 0.75:
                    sesgo_txt = "  [cotiza ALTO — investigar NO]"
                vol_fmt = f"${op['vol_usd']/1_000_000:.1f}M" if op["vol_usd"] >= 1_000_000 else f"${op['vol_usd']/1_000:.0f}K"
                print(f"  [{i}] {op['mercado']}")
                print(f"       YES: {p_yes:.2f}  |  NO: {p_no:.2f}  |  Vol: {vol_fmt}{sesgo_txt}")
                print()
        else:
            print("  Sin candidatos disponibles (API no accesible o sin mercados activos con volumen suficiente).")

    # ── Recordatorio psicológico del día ──────────────────────────────────────
    print()
    titulo("RECORDATORIO PSICOLOGICO DEL DIA")
    if _SESGOS_OK:
        rec = recordatorio_del_dia()
        print(f"  Sesgo del dia: {rec.get('nombre', '')}")
        print(f"  {rec.get('mensaje', '')}")
        if rec.get("antidoto"):
            print(f"\n  Antidoto: {rec['antidoto']}")
    else:
        print("  [!] sesgos_psicologicos.py no disponible.")

    # ── Historial de trades ────────────────────────────────────────────────────
    print()
    mostrar_historial()

    sep("═")
    print()
    print("  USO DEL HISTORIAL DESDE PYTHON:")
    print("  from analizar_portfolio import registrar_trade, resolver_trade, actualizar_trade")
    print("  python analizar_portfolio.py --historial          # solo historial")
    print()


if __name__ == "__main__":
    main()
