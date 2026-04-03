"""
politica_edge.py
Sistema de analisis de mercados politicos en Polymarket.
Protocolo de integridad analitica completo: semaforo, momentum, Kelly, RSS.
"""
import sys
import re
import requests
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACION
# ═══════════════════════════════════════════════════════════════════════════════

GAMMA_API   = "https://gamma-api.polymarket.com"
CLOB_API    = "https://clob.polymarket.com"
POLY_BASE   = "https://polymarket.com/event"

CAPITAL         = 434.24
MAX_POLITICO    = 25.0        # capital maximo por mercado politico
KELLY_FRACCION  = 0.25
VOL_MIN         = 500_000
DIAS_MIN        = 7
DIAS_MAX        = 180
PRECIO_MIN      = 0.05        # 5 centavos
PRECIO_MAX      = 0.95        # 95 centavos
MOMENTUM_7D_UMBRAL    = 10    # pp — señal de nueva informacion
MOMENTUM_24H_UMBRAL   = 20    # pp — posible insider
VOLUMEN_ANOMALO_RATIO = 3.0   # ratio vol24h/promedio para alerta

RSS_POLITICOS = [
    {"nombre": "Reuters Politics",  "url": "https://feeds.reuters.com/Reuters/PoliticsNews",              "nivel": "B"},
    {"nombre": "AP Politics",       "url": "https://rsshub.app/apnews/politics",                          "nivel": "B"},
    {"nombre": "BBC Politics",      "url": "http://feeds.bbci.co.uk/news/politics/rss.xml",               "nivel": "B"},
    {"nombre": "EFE Politica",      "url": "https://www.efe.com/efe/espana/politica/rss",                 "nivel": "B"},
    {"nombre": "Al Jazeera",        "url": "https://www.aljazeera.com/xml/rss/all.xml",                   "nivel": "B"},
]

# Palabras que identifican mercados politicos
KEYWORDS_POLITICOS = [
    "election", "elected", "vote", "voting", "congress", "senate", "house",
    "president", "prime minister", "premier", "chancellor", "parliament",
    "coalition", "party wins", "party lose", "minister", "referendum",
    "impeach", "resign", "approval rating", "polling", "majority",
    "legislation", "bill pass", "executive order", "tariff", "sanction",
    "trump", "biden", "harris", "modi", "macron", "scholz", "sunak",
    "meloni", "orban", "erdogan", "xi jinping", "putin", "zelensky",
    "republican", "democrat", "labour", "tory", "liberal", "conservative",
    "supreme court", "nomination", "confirmation", "filibuster",
    "midterm", "primary", "runoff", "recall", "veto", "pardon",
    "nato", "eu membership", "brexit", "trade deal", "treaty",
    "border", "immigration bill", "debt ceiling", "budget",
    "fed chair", "cabinet", "secretary of state", "attorney general",
    "speaker", "majority leader", "minority leader",
    "election fraud", "recount", "ballot",
]

# Señales de riesgo especificas
KEYWORDS_TRUMP_EFFECT = [
    "trump", "executive order trump", "trump says", "trump announce",
    "trump tweet", "trump sign", "trump declare", "trump order",
]

KEYWORDS_RESOLUCION_AMBIGUA = [
    "successful", "significantly", "major", "likely", "expected",
    "popular", "wins support", "broadly", "substantially",
    "widely seen", "generally considered", "deemed",
]

KEYWORDS_INSIDER = [
    # Detectados historicamente en Polymarket 2025-2026
    "nothingeverfrickinghappens",
]

# Sesgo documentado en mercados europeos (Polymarket 2025)
MERCADOS_SESGO_EUROPEO = [
    "spain", "france", "germany", "hungary", "poland",
    "espana", "alemania", "francia", "hungria",
]


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

def sep(char="─", ancho=68):
    print(char * ancho)

def titulo(texto, char="═", ancho=68):
    print(char * ancho)
    print(f"  {texto}")
    print(char * ancho)

def s(val):
    return "+" if val >= 0 else ""

def truncar(texto, n=65):
    return texto if len(texto) <= n else texto[:n - 3] + "..."

def hoy_utc():
    return datetime.now(timezone.utc).date()

def parsear_fecha_iso(raw):
    if not raw:
        return None
    raw = raw.strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw[:25], fmt)
            return dt.date() if hasattr(dt, "date") else dt
        except ValueError:
            continue
    return None

def dias_hasta(fecha_str):
    try:
        d = datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
        return (d - hoy_utc()).days
    except Exception:
        return None

def float_safe(val, default=0.0):
    try:
        return float(str(val).strip('"\''))
    except Exception:
        return default


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 1 — OBTENER MERCADOS POLITICOS DE POLYMARKET
# ═══════════════════════════════════════════════════════════════════════════════

def es_mercado_politico(pregunta):
    q = pregunta.lower()
    return any(kw in q for kw in KEYWORDS_POLITICOS)

def extraer_precio_yes(mercado):
    import json as _json
    prices   = mercado.get("outcomePrices", [])
    outcomes = mercado.get("outcomes", [])
    # La API puede devolver outcomePrices/outcomes como JSON string en vez de lista
    if isinstance(prices, str):
        try:
            prices = _json.loads(prices)
        except Exception:
            prices = []
    if isinstance(outcomes, str):
        try:
            outcomes = _json.loads(outcomes)
        except Exception:
            outcomes = []
    idx_yes  = 0
    if isinstance(outcomes, list):
        for i, o in enumerate(outcomes):
            if str(o).lower() in ("yes", "true", "si"):
                idx_yes = i
                break
    if isinstance(prices, list) and len(prices) > idx_yes:
        v = float_safe(prices[idx_yes])
        if 0 < v < 1:
            return v
    ltp = mercado.get("lastTradePrice")
    if ltp:
        return float_safe(ltp)
    return None

def obtener_mercados_politicos(verbose=True):
    hoy         = hoy_utc()
    fecha_min   = hoy + timedelta(days=DIAS_MIN)
    fecha_max   = hoy + timedelta(days=DIAS_MAX)
    resultado   = []
    vistos      = set()

    if verbose:
        print("  Descargando mercados de Polymarket...", end=" ", flush=True)

    offset    = 0
    batch     = 100
    max_pages = 30   # hasta 3000 mercados para cubrir categorias politicas

    for _ in range(max_pages):
        try:
            r = requests.get(
                f"{GAMMA_API}/markets",
                params={
                    "active":    "true",
                    "closed":    "false",
                    "limit":     batch,
                    "offset":    offset,
                    "order":     "volumeNum",
                    "ascending": "false",
                },
                timeout=15,
            )
            if r.status_code != 200:
                break
            datos = r.json()
            if not datos:
                break

            for m in datos:
                vol = float_safe(m.get("volumeNum", 0))

                # Abandonar cuando los volumenes bajan de nuestro minimo
                if vol < VOL_MIN:
                    if verbose:
                        print(f"OK")
                    return resultado

                pregunta = m.get("question", "")
                mid = m.get("id", "")

                if mid in vistos or not es_mercado_politico(pregunta):
                    continue
                vistos.add(mid)

                # Filtrar por fecha
                end_raw = m.get("endDateIso") or m.get("endDate", "")
                if not end_raw:
                    continue
                try:
                    end_date = datetime.strptime(end_raw[:10], "%Y-%m-%d").date()
                except Exception:
                    continue
                if not (fecha_min <= end_date <= fecha_max):
                    continue

                # Filtrar por precio
                precio_yes = extraer_precio_yes(m)
                if precio_yes is None or not (PRECIO_MIN <= precio_yes <= PRECIO_MAX):
                    continue

                resultado.append(m)

            offset += batch

        except Exception as e:
            if verbose:
                print(f"\n  Error pagina offset={offset}: {e}")
            break

    if verbose:
        print("OK")
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 2 — SEMAFORO DE INTEGRIDAD
# ═══════════════════════════════════════════════════════════════════════════════

def detectar_sesgo_europeo(pregunta):
    q = pregunta.lower()
    return any(pais in q for pais in MERCADOS_SESGO_EUROPEO)

def clasificar_semaforo(mercado, precio_yes):
    pregunta    = mercado.get("question", "").lower()
    desc        = str(mercado.get("description", "")).lower()
    texto       = pregunta + " " + desc
    vol         = float_safe(mercado.get("volumeNum", 0))
    created_raw = mercado.get("createdAt", "")
    razones_rojo     = []
    razones_amarillo = []
    razones_verde    = []

    # ── ROJO ──────────────────────────────────────────────────────────────────

    # Precio extremo (>85%)
    if precio_yes > 0.85 or precio_yes < 0.15:
        razones_rojo.append(f"Precio extremo ({precio_yes:.0%}) — poco retorno para el riesgo")

    # Resolucion subjetiva
    if any(kw in texto for kw in KEYWORDS_RESOLUCION_AMBIGUA):
        kws = [kw for kw in KEYWORDS_RESOLUCION_AMBIGUA if kw in texto]
        razones_rojo.append(f"Resolucion posiblemente subjetiva: '{kws[0]}'")

    # Correlacion directa con Iran/mercados militares
    if any(w in texto for w in ["iran", "hormuz", "tehran", "ceasefire iran"]):
        razones_rojo.append("Correlacion directa con conflicto Iran — no entrar en paralelo a posiciones abiertas")

    # Insider conocido
    if any(kw in texto for kw in KEYWORDS_INSIDER):
        razones_rojo.append("Insider trading documentado en este mercado")

    # Volumen muy bajo
    if vol < 500_000:
        razones_rojo.append(f"Volumen insuficiente (${vol:,.0f})")

    if razones_rojo:
        return "ROJO", razones_rojo + razones_amarillo

    # ── AMARILLO ──────────────────────────────────────────────────────────────

    # Trump effect
    if any(kw in texto for kw in KEYWORDS_TRUMP_EFFECT):
        razones_amarillo.append("RIESGO TRUMP EFFECT — declaraciones no modelizables (+/-15% incertidumbre)")

    # Definicion ambigua (nivel leve)
    if any(w in texto for w in ["could", "might", "possible", "may", "perhaps", "if "]):
        razones_amarillo.append("Lenguaje condicional en la pregunta — verificar reglas exactas de resolucion")

    # Volumen bajo pero aceptable ($500K-$2M) para elecciones
    if any(w in texto for w in ["election", "vote", "ballot", "elected"]) and vol < 2_000_000:
        razones_amarillo.append(f"Elecciones con vol <$2M (${vol/1e6:.1f}M) — manipulable, reducir posicion 50%")

    # Mercado nuevo
    if created_raw:
        try:
            created = datetime.strptime(created_raw[:10], "%Y-%m-%d").date()
            antiguedad = (hoy_utc() - created).days
            if antiguedad < 30:
                razones_amarillo.append(f"Mercado nuevo ({antiguedad} dias) — precio puede no reflejar toda la informacion")
        except Exception:
            pass

    # Sesgo europeo documentado
    if detectar_sesgo_europeo(pregunta):
        razones_amarillo.append("Mercado europeo — sesgo pro-liberal documentado en Polymarket 2025. Ajustar +5pp a prob conservadora")

    if razones_amarillo:
        return "AMARILLO", razones_amarillo

    # ── VERDE ─────────────────────────────────────────────────────────────────

    # Evento con fecha fija
    if any(w in texto for w in ["election", "vote", "summit", "deadline", "hearing", "session"]):
        razones_verde.append("Evento con fecha fija — resolucion predecible")

    # Alta liquidez
    if vol > 5_000_000:
        razones_verde.append(f"Alta liquidez (${vol/1e6:.1f}M) — precio refleja informacion del mercado")

    # Fuente oficial verificable probable
    if any(w in texto for w in ["congress", "senate", "parliament", "court", "official", "certified"]):
        razones_verde.append("Resolucion probable basada en fuente oficial verificable")

    razones_verde.append("Sin señales de riesgo identificadas automaticamente")
    return "VERDE", razones_verde


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 3 — FUENTES RSS POLITICAS
# ═══════════════════════════════════════════════════════════════════════════════

def parsear_feed_politico(feed_info, timeout=10):
    items_out = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PoliticaBot/1.0)"}
        r = requests.get(feed_info["url"], headers=headers, timeout=timeout)
        if r.status_code != 200:
            return items_out
        content = r.content.replace(b' xmlns="', b' xmlnsx="')
        root    = ET.fromstring(content)
        for item in root.findall(".//item"):
            t = item.findtext("title", "").strip()
            d = item.findtext("description", "").strip()
            l = item.findtext("link", "").strip()
            p = item.findtext("pubDate", "").strip()
            if t:
                items_out.append({
                    "fuente": feed_info["nombre"],
                    "nivel":  feed_info["nivel"],
                    "titulo": t,
                    "desc":   d,
                    "link":   l,
                    "fecha":  p,
                })
    except Exception:
        pass
    return items_out

def obtener_noticias_politicas():
    todas = []
    for feed in RSS_POLITICOS:
        todas.extend(parsear_feed_politico(feed))
    return todas

def temas_trending(noticias, top_n=5):
    """Extrae los N temas politicos mas mencionados hoy en los RSS."""
    stopwords = {
        "the","a","an","in","on","at","to","for","of","and","or","is","are",
        "was","were","has","have","had","be","been","being","will","would",
        "could","should","may","might","can","that","this","these","those",
        "with","from","by","as","it","its","not","but","so","do","did",
        "also","after","before","over","under","into","than","more","most",
        "about","said","says","say","tells","told","report","reports",
        "un","una","los","las","del","con","por","para","que","en","es","se",
        "el","la","le","les","des","une","sur","dans","avec","qui","que","est",
    }
    palabras = []
    for n in noticias:
        texto = (n["titulo"] + " " + n.get("desc", "")).lower()
        tokens = re.findall(r"\b[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{4,}\b", texto)
        palabras.extend([t for t in tokens if t not in stopwords])
    conteo = Counter(palabras)
    # Filtrar por relevancia politica
    politicos = [(w, c) for w, c in conteo.most_common(100)
                 if any(kw in w for kw in ["trump","iran","elect","vote","congress",
                                            "senate","presid","minist","chancellor",
                                            "tariff","sanction","border","immigr",
                                            "nuclear","nato","trade","budget","tax",
                                            "court","law","bill","parti","coalit"])]
    return politicos[:top_n]

def buscar_mercado_polymarket(tema, mercados_cache):
    """Busca en el cache de mercados si hay alguno relacionado con el tema."""
    tema_lower = tema.lower()
    matches = []
    for m in mercados_cache:
        q = m.get("question", "").lower()
        if tema_lower in q or any(w in q for w in tema_lower.split()):
            matches.append(m)
    return matches[:2]


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 4 — MOMENTUM, VOLUMEN ANOMALO Y ARBITRAJE
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_momentum(mercado, precio_yes_actual):
    """
    Usa los campos de cambio de precio que devuelve la Gamma API.
    oneDayPriceChange  : cambio porcentual en 24h
    oneWeekPriceChange : cambio porcentual en 7 dias
    """
    cambio_7d  = float_safe(mercado.get("oneWeekPriceChange",  0)) * 100
    cambio_24h = float_safe(mercado.get("oneDayPriceChange",   0)) * 100
    # La API devuelve cambio relativo (ej: -0.05 = -5pp)
    # Convertimos a cambio absoluto en puntos porcentuales
    precio_7d_aprox = precio_yes_actual - (cambio_7d / 100)

    señales = []
    if abs(cambio_7d) > MOMENTUM_7D_UMBRAL:
        dir7 = "subiendo" if cambio_7d > 0 else "bajando"
        señales.append(f"Momentum 7d: {s(cambio_7d)}{cambio_7d:.1f}pp ({dir7}) — nueva informacion probable")
    if abs(cambio_24h) > MOMENTUM_24H_UMBRAL:
        dir24 = "subiendo" if cambio_24h > 0 else "bajando"
        señales.append(f"Movimiento 24h: {s(cambio_24h)}{cambio_24h:.1f}pp ({dir24}) — POSIBLE INSIDER, investigar")

    return cambio_7d, cambio_24h, señales

def calcular_volumen_anomalo(mercado):
    """
    vol24h vs volumeNum/dias_activo como proxy del promedio diario.
    """
    vol_total = float_safe(mercado.get("volumeNum", 0))
    vol_24h   = float_safe(mercado.get("volume24hr", 0))
    created   = mercado.get("createdAt", "")
    señales   = []
    ratio     = None

    if vol_total > 0 and vol_24h > 0 and created:
        try:
            dias_activo = max(1, (hoy_utc() - datetime.strptime(created[:10], "%Y-%m-%d").date()).days)
            vol_diario_prom = vol_total / dias_activo
            if vol_diario_prom > 0:
                ratio = vol_24h / vol_diario_prom
                if ratio >= VOLUMEN_ANOMALO_RATIO:
                    señales.append(f"Volumen anomalo: {ratio:.1f}x el promedio diario — algo esta pasando, investigar antes de entrar")
        except Exception:
            pass

    return vol_24h, ratio, señales

def detectar_inconsistencias(mercados_lista):
    """
    Busca pares de mercados matematicamente inconsistentes.
    Ejemplo: P(X gana eleccion) > suma de P(X candidatos individuales)
    """
    inconsistencias = []
    # Agrupar por palabras clave comunes
    grupos = {}
    for m in mercados_lista:
        q    = m.get("question", "")
        slug = m.get("slug", "")
        # Extraer pais/evento como clave
        for kw in ["election", "president", "prime minister", "chancellor"]:
            if kw in q.lower():
                clave = q.lower()[:30]
                grupos.setdefault(clave, []).append(m)

    for clave, grupo in grupos.items():
        if len(grupo) >= 2:
            precios = []
            for m in grupo:
                p = extraer_precio_yes(m)
                if p is not None:
                    precios.append((m.get("question", "")[:50], p))
            if len(precios) >= 2:
                # Si un mercado madre tiene precio < hijo, inconsistencia
                precios.sort(key=lambda x: x[1], reverse=True)
                if precios[0][1] < precios[1][1] - 0.05:
                    inconsistencias.append({
                        "mercado_a": precios[0][0],
                        "precio_a":  precios[0][1],
                        "mercado_b": precios[1][0],
                        "precio_b":  precios[1][1],
                        "nota":      "Inconsistencia detectada — arbitraje potencial"
                    })

    return inconsistencias


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 5 — KELLY Y ACCION
# ═══════════════════════════════════════════════════════════════════════════════

def estimar_prob_propia(precio_yes, semaforo, razones, sesgo_europeo):
    """
    Estimacion conservadora de probabilidad propia.
    En produccion, reemplazar con analisis manual de fuentes A/B.
    Ajustes automaticos basados en señales del protocolo.
    """
    prob = precio_yes  # punto de partida: precio de mercado

    # Ajustes por señales
    for r in razones:
        if "trump effect" in r.lower():
            prob = prob * 0.92  # -8% por imprevisibilidad
        if "manipulable" in r.lower() or "volumen" in r.lower():
            prob = prob * 0.90
        if "ambigua" in r.lower() or "subjetiva" in r.lower():
            prob = prob * 0.85
        if "momentum" in r.lower() and "insider" in r.lower():
            prob = prob * 0.88

    # Sesgo europeo: ajustar hacia conservador
    if sesgo_europeo:
        prob = max(0.05, prob - 0.05)

    return round(min(0.95, max(0.05, prob)), 3)

def calcular_kelly_accion(prob_propia, precio_yes, semaforo, vol):
    """
    Calcula Kelly ajustado y genera recomendacion de accion.
    Toma posicion en YES si prob_propia > precio_yes, en NO si menor.
    """
    # Decidir direccion
    if prob_propia >= precio_yes:
        direccion   = "YES"
        p           = prob_propia
        precio_lado = precio_yes
    else:
        direccion   = "NO"
        p           = 1 - prob_propia
        precio_lado = 1 - precio_yes

    edge_pp = abs(prob_propia - precio_yes) * 100

    if edge_pp < 8:
        return edge_pp, direccion, 0, "ESPERAR", "BAJA"

    odds           = (1 - precio_lado) / precio_lado if precio_lado < 1 else 0
    kelly_completo = (p - (1 - p) / odds) if odds > 0 else 0
    kelly_ajustado = max(0, kelly_completo * KELLY_FRACCION)
    capital_raw    = CAPITAL * kelly_ajustado
    capital_final  = min(capital_raw, MAX_POLITICO)

    # Ajustes por semaforo
    if semaforo == "AMARILLO":
        capital_final *= 0.5
    if vol < 2_000_000 and any(w in ["election", "vote", "ballot"] for w in [""]):
        capital_final *= 0.5

    capital_final = round(max(0, capital_final), 2)

    if edge_pp >= 20:
        confianza = "ALTA"
        accion    = "ENTRAR" if semaforo != "ROJO" else "EVITAR"
    elif edge_pp >= 12:
        confianza = "MEDIA"
        accion    = "INVESTIGAR" if semaforo == "AMARILLO" else "ENTRAR"
    else:
        confianza = "BAJA"
        accion    = "ESPERAR"

    if semaforo == "ROJO":
        accion    = "EVITAR"
        confianza = "—"

    return edge_pp, direccion, capital_final, accion, confianza


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 6 — TRENDING POLITICO
# ═══════════════════════════════════════════════════════════════════════════════

def seccion_trending(noticias, mercados_todos):
    titulo("PASO 6 — TRENDING POLITICO GLOBAL  [Reuters · EFE · AP · BBC]")

    if not noticias:
        print("  Sin noticias disponibles en feeds RSS.")
        return

    temas = temas_trending(noticias, top_n=5)
    if not temas:
        print("  No se identificaron temas trending con palabras clave politicas.")
        return

    print(f"  {len(noticias)} noticias procesadas de feeds politicos\n")

    for i, (tema, conteo) in enumerate(temas, 1):
        sep()
        print(f"  [{i}] TEMA TRENDING: '{tema.upper()}'  ({conteo} menciones)")

        # Buscar mercado en Polymarket
        matches = buscar_mercado_polymarket(tema, mercados_todos)
        if matches:
            for m in matches:
                p_yes = extraer_precio_yes(m)
                vol   = float_safe(m.get("volumeNum", 0))
                end   = (m.get("endDateIso") or m.get("endDate", ""))[:10]
                slug  = m.get("slug", m.get("id", ""))
                print(f"       Mercado encontrado: {truncar(m.get('question',''), 60)}")
                if p_yes is not None:
                    print(f"       Precio YES: {p_yes:.0%}  |  Vol: ${vol:,.0f}  |  Vence: {end}")
                    print(f"       URL: {POLY_BASE}/{slug}")
                    # Edge potencial rapido
                    _, _, capital, accion, conf = calcular_kelly_accion(p_yes, p_yes, "AMARILLO", vol)
                    print(f"       Edge preliminar: insuficiente para accion sin analisis A/B")
        else:
            print(f"       Sin mercado activo en Polymarket — OPORTUNIDAD DE MERCADO NUEVO")
            print(f"       Los mercados nuevos sobre temas trending tienen ineficiencias en primeros dias")
            # Mostrar noticia mas reciente sobre el tema
            nots_rel = [n for n in noticias if tema in n["titulo"].lower()]
            if nots_rel:
                n = nots_rel[0]
                print(f"       Noticia: [{n['fuente']}] {truncar(n['titulo'], 60)}")

    sep()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    titulo(f"SISTEMA DE ANALISIS POLITICO — POLYMARKET  [{ahora}]")
    print(f"  Capital referencia: ${CAPITAL}  |  Max por mercado: ${MAX_POLITICO}")
    print(f"  Filtros: Vol >${VOL_MIN/1e6:.1f}M  |  {DIAS_MIN}-{DIAS_MAX} dias  |  Precio {PRECIO_MIN:.0%}-{PRECIO_MAX:.0%}")
    print()

    # ── 1. Obtener mercados ────────────────────────────────────────────────────
    titulo("PASO 1 — OBTENIENDO MERCADOS POLITICOS")
    mercados = obtener_mercados_politicos(verbose=True)
    print(f"  Mercados politicos encontrados: {len(mercados)}")
    if not mercados:
        print("  Sin mercados con los filtros actuales. Intenta bajar VOL_MIN.")
        return
    print()

    # ── 2-4. Analizar cada mercado ────────────────────────────────────────────
    titulo("PASOS 2-4 — ANALISIS + SEMAFORO + MOMENTUM")

    analizados = []
    for m in mercados:
        precio_yes = extraer_precio_yes(m)
        if precio_yes is None:
            continue

        semaforo, razones  = clasificar_semaforo(m, precio_yes)
        cambio_7d, cambio_24h, señales_momentum = calcular_momentum(m, precio_yes)
        vol_24h, ratio_vol, señales_vol = calcular_volumen_anomalo(m)
        sesgo_eu  = detectar_sesgo_europeo(m.get("question", ""))
        prob_prop = estimar_prob_propia(precio_yes, semaforo, razones, sesgo_eu)
        vol_total = float_safe(m.get("volumeNum", 0))
        edge_pp, direccion, capital, accion, confianza = calcular_kelly_accion(
            prob_prop, precio_yes, semaforo, vol_total
        )

        analizados.append({
            "mercado":      m,
            "precio_yes":   precio_yes,
            "semaforo":     semaforo,
            "razones":      razones,
            "cambio_7d":    cambio_7d,
            "cambio_24h":   cambio_24h,
            "señales_mom":  señales_momentum,
            "vol_24h":      vol_24h,
            "ratio_vol":    ratio_vol,
            "señales_vol":  señales_vol,
            "sesgo_eu":     sesgo_eu,
            "prob_prop":    prob_prop,
            "edge_pp":      edge_pp,
            "direccion":    direccion,
            "capital":      capital,
            "accion":       accion,
            "confianza":    confianza,
        })

    # Ordenar: primero VERDE, luego AMARILLO, luego ROJO; dentro de cada grupo por edge
    orden_semaforo = {"VERDE": 0, "AMARILLO": 1, "ROJO": 2}
    analizados.sort(key=lambda x: (orden_semaforo[x["semaforo"]], -x["edge_pp"]))

    # Detectar inconsistencias entre mercados
    inconsistencias = detectar_inconsistencias(mercados)

    # ── 5. Output de los mejores 5 mercados ────────────────────────────────────
    titulo("PASO 5 — TOP 5 MERCADOS POLITICOS")

    iconos = {"VERDE": "[V]", "AMARILLO": "[~]", "ROJO": "[X]"}
    labels = {"VERDE": "VERDE — posible edge", "AMARILLO": "AMARILLO — analizar con cautela", "ROJO": "ROJO — evitar"}

    mostrados = 0
    for a in analizados:
        if mostrados >= 5:
            break
        # Mostrar todos los verdes y amarillos; rojos solo si hay pocos verdes
        if a["semaforo"] == "ROJO" and mostrados >= 3:
            continue

        m         = a["mercado"]
        p_yes     = a["precio_yes"]
        p_no      = 1 - p_yes
        vol       = float_safe(m.get("volumeNum", 0))
        end_raw   = (m.get("endDateIso") or m.get("endDate", ""))[:10]
        dias      = dias_hasta(end_raw) or "?"
        slug      = m.get("slug") or m.get("id", "")
        icono     = iconos[a["semaforo"]]
        label     = labels[a["semaforo"]]

        sep()
        print(f"  MERCADO  : {truncar(m.get('question',''), 65)}")
        print(f"  URL      : {POLY_BASE}/{slug}")
        print(f"  SEMAFORO : {icono} {label}")
        sep()
        print(f"  Precio YES : {p_yes:.0%}   |   Precio NO : {p_no:.0%}")
        print(f"  Volumen    : ${vol:>12,.0f}")
        print(f"  Dias hasta resolucion : {dias}")
        if a["cambio_7d"] != 0:
            print(f"  Momentum 7d: {s(a['cambio_7d'])}{a['cambio_7d']:.1f}pp  |  Momentum 24h: {s(a['cambio_24h'])}{a['cambio_24h']:.1f}pp")
        if a["vol_24h"] > 0:
            ratio_str = f"  ({a['ratio_vol']:.1f}x promedio)" if a["ratio_vol"] else ""
            print(f"  Vol 24h    : ${a['vol_24h']:,.0f}{ratio_str}")
        sep()
        print(f"  ANALISIS:")
        print(f"  Fuentes consultadas : Reuters [B] · AP [B] · EFE [B] · BBC [B] · Polymarket Gamma API")
        print(f"  NOTA: Completar con fuentes Nivel A (FiveThirtyEight, parlamentos oficiales)")
        print(f"  Prob. propia estimada: {a['prob_prop']:.0%}  (precio mercado: {p_yes:.0%})")
        print(f"  Edge calculado: {s(a['edge_pp'])}{a['edge_pp']:.1f}pp")
        if a["sesgo_eu"]:
            print(f"  [!] Sesgo europeo aplicado: -5pp ajuste conservador")

        # Razones del semaforo
        print(f"\n  Senales identificadas:")
        for r in a["razones"][:4]:
            print(f"    - {r}")
        for s_m in a["señales_mom"]:
            print(f"    - {s_m}")
        for s_v in a["señales_vol"]:
            print(f"    - {s_v}")
        if a["sesgo_eu"]:
            print(f"    - Pais europeo — ajuste sesgo Polymarket aplicado")

        sep()
        print(f"  ACCION RECOMENDADA:")
        print(f"  Capital sugerido (Kelly 25%): ${a['capital']:.2f}")
        print(f"  Posicion  : {a['direccion']}")
        print(f"  Accion    : {a['accion']}")
        print(f"  Confianza : {a['confianza']}")
        if a["accion"] in ("ENTRAR", "INVESTIGAR"):
            print(f"  ANTES DE ENTRAR: Verificar reglas exactas de resolucion en Polymarket")
            print(f"  ANTES DE ENTRAR: Calcular prob propia con fuentes Nivel A (FiveThirtyEight, parlamento oficial)")
        print()
        mostrados += 1

    # ── Inconsistencias de arbitraje ──────────────────────────────────────────
    if inconsistencias:
        print()
        titulo("ARBITRAJE — INCONSISTENCIAS DETECTADAS")
        for inc in inconsistencias[:3]:
            sep()
            print(f"  Mercado A : {truncar(inc['mercado_a'], 60)}  => {inc['precio_a']:.0%}")
            print(f"  Mercado B : {truncar(inc['mercado_b'], 60)}  => {inc['precio_b']:.0%}")
            print(f"  Nota      : {inc['nota']}")
        sep()

    # ── Resumen semaforos ─────────────────────────────────────────────────────
    print()
    titulo("RESUMEN SEMAFOROS")
    verdes    = sum(1 for a in analizados if a["semaforo"] == "VERDE")
    amarillos = sum(1 for a in analizados if a["semaforo"] == "AMARILLO")
    rojos     = sum(1 for a in analizados if a["semaforo"] == "ROJO")
    print(f"  Total mercados analizados : {len(analizados)}")
    print(f"  [V] VERDE    (posible edge)         : {verdes}")
    print(f"  [~] AMARILLO (analizar con cautela) : {amarillos}")
    print(f"  [X] ROJO     (evitar)               : {rojos}")
    print()

    # ── 6. Trending politico ──────────────────────────────────────────────────
    print("  Obteniendo noticias politicas de RSS...", end=" ", flush=True)
    noticias_pol = obtener_noticias_politicas()
    print(f"{sum(1 for f in RSS_POLITICOS for _ in [1])} feeds consultados, {len(noticias_pol)} noticias\n")
    seccion_trending(noticias_pol, mercados)

    # ── Reglas de oro ─────────────────────────────────────────────────────────
    titulo("REGLAS DE ORO — RECORDATORIO")
    reglas = [
        "NUNCA recomendar mercados sobre declaraciones Trump sin marcar 'RIESGO TRUMP EFFECT'",
        "NUNCA entrar en elecciones con vol <$2M — demasiado manipulables",
        "SIEMPRE verificar reglas exactas de resolucion antes de cualquier entrada",
        "SIEMPRE buscar mercado inverso para detectar inconsistencias matematicas",
        "Mercados europeos: +5pp ajuste conservador (sesgo pro-liberal documentado 2025)",
        f"Capital maximo por mercado politico: ${MAX_POLITICO} USDC salvo edge >25pp con fuente Nivel A",
        "Sin liquidez disponible ($0.01) — resolver antes de cualquier nueva posicion",
    ]
    for r in reglas:
        print(f"  - {r}")
    print()


if __name__ == "__main__":
    main()
