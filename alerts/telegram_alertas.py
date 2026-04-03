# -*- coding: utf-8 -*-
"""
telegram_alertas.py — Resumen diario inteligente + Sniper de corto plazo
=========================================================================
CLI:
  python telegram_alertas.py --diario     → envia resumen completo del dia
  python telegram_alertas.py --check      → check rapido precios + noticias
  python telegram_alertas.py --sniper     → modo continuo busca gangas <15 dias
  python telegram_alertas.py --test       → envia mensaje de prueba
"""

import sys, os
sys.path.insert(0, "C:\\inversiones")

import io, json, time, datetime, requests
import yfinance as yf
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()
TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

GAMMA_API  = "https://gamma-api.polymarket.com"
LOG_DIR    = os.path.join("C:\\inversiones", "logs")
PORTFOLIO  = [
    {"slug": "us-x-iran-ceasefire-by-april-15-182-528-637",
     "nombre": "Ceasefire Apr15", "dir": "NO", "entrada": 0.657,
     "shares": 304.3, "resuelve": "15 abr", "invertir": False},
    # Pos 2: proxy via 'regime fall' invertido — si regimen NO cae = conflicto NO termina
    {"slug": "will-the-iranian-regime-fall-by-june-30",
     "nombre": "Conflict Jun30",  "dir": "NO", "entrada": 0.24,
     "shares": 558.8, "resuelve": "30 jun", "invertir": True},
]

# ==========================================
# TELEGRAM
# ==========================================
def _send(msg: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg,
                                     "parse_mode": "HTML",
                                     "disable_web_page_preview": True}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram error] {e}")
        return False

# ==========================================
# PRECIOS
# ==========================================
def _precio_no(slug: str, invertir: bool = False) -> float:
    try:
        r = requests.get(f"{GAMMA_API}/markets?slug={slug}", timeout=10)
        d = r.json()
        if d:
            prices = json.loads(d[0].get("outcomePrices", "[0.5,0.5]"))
            p_no = float(prices[1]) if len(prices) > 1 else 1 - float(prices[0])
            return round(1 - p_no, 4) if invertir else p_no
    except:
        pass
    return None

def _brent() -> float:
    try:
        return yf.Ticker("BZ=F").fast_info["last_price"]
    except:
        return None

def _vix() -> float:
    try:
        return yf.Ticker("^VIX").fast_info["last_price"]
    except:
        return None

def _gold() -> float:
    try:
        return yf.Ticker("GC=F").fast_info["last_price"]
    except:
        return None

# ==========================================
# NOTICIAS DEL DIA (desde log de bot_inteligencia)
# ==========================================
def _leer_noticias_hoy() -> list:
    """Lee logs/noticias_HOY.txt y devuelve lista de noticias del dia."""
    hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    ruta = os.path.join(LOG_DIR, f"noticias_{hoy}.txt")
    noticias = []
    if not os.path.exists(ruta):
        return []
    with open(ruta, "r", encoding="utf-8") as f:
        bloque = {}
        for linea in f:
            linea = linea.rstrip()
            if linea.startswith("[") and "] [" in linea:
                # Formato: [HH:MM] [Agencia] Titulo
                try:
                    hora  = linea[1:6]
                    resto = linea[8:]
                    agencia_fin = resto.index("]")
                    agencia = resto[1:agencia_fin]
                    titulo  = resto[agencia_fin+2:]
                    bloque  = {"hora": hora, "agencia": agencia, "titulo": titulo, "sesgo": ""}
                except:
                    pass
            elif linea.startswith("  Sesgo:") and bloque:
                bloque["sesgo"] = linea.replace("  Sesgo:", "").split("|")[0].strip()
                noticias.append(bloque)
                bloque = {}
    return noticias

def _resumir_noticias(noticias: list) -> str:
    """Agrupa y filtra las noticias más relevantes para el resumen diario."""
    if not noticias:
        return "  <i>Sin noticias registradas hoy. Bot en monitoreo.</i>"

    # Agrupar por keyword más importante
    prioritarias = []
    relevantes   = []
    kw_alta = ["ceasefire", "tregua", "hormuz", "deal", "acuerdo", "strike", "iran"]
    for n in noticias:
        t = n["titulo"].lower()
        if any(k in t for k in kw_alta):
            prioritarias.append(n)
        else:
            relevantes.append(n)

    lineas = []
    # Máximo 5 noticias: prioridad a las de alta relevancia
    mostrar = (prioritarias + relevantes)[:5]
    bloques_vistos = set()
    for n in mostrar:
        key = n["titulo"][:40]
        if key in bloques_vistos:
            continue
        bloques_vistos.add(key)
        # Emoji según sesgo
        if "Propaganda" in n["sesgo"] or "Nivel C" in n["sesgo"]:
            em = "🔴"
        elif "Occidente" in n["sesgo"]:
            em = "🔵"
        elif "Oriente" in n["sesgo"]:
            em = "🟡"
        else:
            em = "⚪"
        lineas.append(f"  {em} [{n['agencia']}] {n['titulo'][:70]}")

    total_extra = max(0, len(noticias) - 5)
    resultado = "\n".join(lineas)
    if total_extra:
        resultado += f"\n  <i>...y {total_extra} noticias más en logs/noticias_{datetime.datetime.now().strftime('%Y-%m-%d')}.txt</i>"
    return resultado

# ==========================================
# RESUMEN DIARIO
# ==========================================
def enviar_resumen_diario():
    """Construye y envía el resumen completo del dia en UN solo mensaje."""
    print("Construyendo resumen diario...")
    ahora = datetime.datetime.now()

    # -- Precios portfolio --
    total_pl    = 0
    lineas_port = []
    for pos in PORTFOLIO:
        p_no = _precio_no(pos["slug"], invertir=pos.get("invertir", False))
        if p_no is None:
            lineas_port.append(f"  • {pos['nombre']}: precio no disponible")
            continue
        coste    = pos["entrada"] * pos["shares"]
        valor    = p_no * pos["shares"]
        pl       = valor - coste
        total_pl += pl
        em = "✅" if pl > 0 else "🔴"
        lineas_port.append(
            f"  {em} {pos['nombre']} ({pos['resuelve']}): "
            f"NO={p_no*100:.0f}% | P/L <b>{'+' if pl>=0 else ''}{pl:.0f}$</b>"
        )

    # -- Macro --
    brent = _brent()
    vix   = _vix()
    gold  = _gold()

    # -- Fear & Greed simple --
    fg = 50
    if brent:
        fg += 15 if brent > 100 else (5 if brent > 85 else -10)
    if vix:
        fg += 15 if vix > 28 else (5 if vix > 20 else -10)
    if gold:
        fg += 8 if gold > 3500 else (3 if gold > 2800 else -5)
    fg = max(0, min(100, fg))
    if   fg >= 75: fg_str = f"🔴 MIEDO EXTREMO ({fg}/100)"
    elif fg >= 55: fg_str = f"🟠 TENSION ({fg}/100)"
    elif fg >= 40: fg_str = f"🟡 INCERTIDUMBRE ({fg}/100)"
    else:          fg_str = f"🟢 CALMA ({fg}/100)"

    # -- Dias hasta deadlines --
    hoy = ahora.date()
    d_trump  = (datetime.date(2026, 4, 6)  - hoy).days
    d_apr15  = (datetime.date(2026, 4, 15) - hoy).days
    d_jun30  = (datetime.date(2026, 6, 30) - hoy).days

    # -- Noticias del dia --
    noticias    = _leer_noticias_hoy()
    resumen_nws = _resumir_noticias(noticias)

    # -- Construir mensaje --
    sep  = "─" * 28
    msg  = f"📊 <b>RESUMEN DIARIO — {ahora.strftime('%d/%m %H:%M')}</b>\n"
    msg += f"{sep}\n\n"

    msg += f"💼 <b>PORTFOLIO</b>\n"
    msg += "\n".join(lineas_port) + "\n"
    pl_str = f"+{total_pl:.0f}$" if total_pl >= 0 else f"{total_pl:.0f}$"
    msg += f"  📈 <b>P/L Total: {pl_str}</b>\n\n"

    msg += f"📉 <b>MACRO</b>\n"
    if brent: msg += f"  ⛽ Brent: <b>${brent:.2f}</b>\n"
    if vix:   msg += f"  📊 VIX:   <b>{vix:.1f}</b>\n"
    if gold:  msg += f"  🥇 Gold:  <b>${gold:.0f}</b>\n"
    msg += f"  🧠 Fear & Greed: {fg_str}\n\n"

    msg += f"⏰ <b>DEADLINES</b>\n"
    msg += f"  🔴 Trump decide strikes: <b>{d_trump}d</b> (6 abr)\n"
    msg += f"  🟡 Ceasefire Apr15: <b>{d_apr15}d</b>\n"
    msg += f"  ⚪ Conflict Jun30: <b>{d_jun30}d</b>\n\n"

    msg += f"📰 <b>NOTICIAS HOY</b> ({len(noticias)} registradas)\n"
    msg += resumen_nws + "\n\n"

    msg += f"<i>Bots activos: intel (15min) · motor (2h) · resumen (9h)</i>"

    ok = _send(msg)
    print(f"  → Resumen diario {'enviado ✅' if ok else 'ERROR ❌'}")
    print(f"  → P/L total: {pl_str} | Noticias: {len(noticias)}")
    return ok

# ==========================================
# CHECK RAPIDO
# ==========================================
def check_rapido():
    """Check rápido: precios actuales + alerta si algo cambió >5pp."""
    print("Check rápido de precios...")
    alertas = []

    for pos in PORTFOLIO:
        p_no = _precio_no(pos["slug"], invertir=pos.get("invertir", False))
        if p_no is None:
            continue
        # Alerta si precio NO cae por debajo de 75% (posible riesgo)
        if pos["dir"] == "NO" and p_no < 0.75:
            alertas.append(
                f"⚠️ <b>{pos['nombre']}</b>: NO bajó a <b>{p_no*100:.0f}%</b> — revisar posición"
            )
        elif pos["dir"] == "NO" and p_no > 0.92:
            alertas.append(
                f"✅ <b>{pos['nombre']}</b>: NO en <b>{p_no*100:.0f}%</b> — posición muy fuerte"
            )

    brent = _brent()
    if brent and brent < 85:
        alertas.append(f"🛢️ <b>Brent bajo:</b> ${brent:.2f} — señal de distensión, revisar NO positions")
    elif brent and brent > 115:
        alertas.append(f"🛢️ <b>Brent alto:</b> ${brent:.2f} — conflicto intensificado")

    if alertas:
        msg = "⚡ <b>CHECK RÁPIDO — Alertas activas</b>\n\n" + "\n".join(alertas)
        _send(msg)
        print(f"  → {len(alertas)} alertas enviadas")
    else:
        print("  → Sin alertas. Todo estable.")

# ==========================================
# DIGEST DE NOTICIAS — TOP 10 ANTI-SESGO
# ==========================================

# Fuentes VERIFICADAS: independientes, sin financiacion estatal significativa
# Excluidas por sesgo: TASS, Xinhua, RT, IRNA, Press TV, Al Mayadeen
FUENTES_RSS = {
    # NIVEL A — Maxima independencia editorial
    "CNBC":            ("https://www.cnbc.com/id/100727362/device/rss/rss.html", 3, "⚪"),
    "CNBC Markets":    ("https://www.cnbc.com/id/10000664/device/rss/rss.html",  3, "⚪"),
    "Guardian World":  ("https://www.theguardian.com/world/rss",                 3, "⚪"),
    "Guardian Biz":    ("https://www.theguardian.com/business/rss",              3, "⚪"),
    "FT":              ("https://www.ft.com/world?format=rss",                   3, "⚪"),
    # NIVEL B — Alta calidad, ligero sesgo occidental
    "BBC MidEast":     ("http://feeds.bbci.co.uk/news/world/middle_east/rss.xml",2, "🔵"),
    "BBC Business":    ("http://feeds.bbci.co.uk/news/business/rss.xml",         2, "🔵"),
    "Al-Monitor":      ("https://www.al-monitor.com/rss",                        2, "🟡"),
    "Politico World":  ("https://rss.politico.com/politics-news.xml",            2, "🔵"),
    "NPR World":       ("https://feeds.npr.org/1004/rss.xml",                    2, "🔵"),
    "Foreign Policy":  ("https://foreignpolicy.com/feed/",                       2, "🔵"),
}

# Puntuacion de impacto por keyword en el titulo
KEYWORDS_IMPACTO = {
    # Impacto MAXIMO en mercados (3 pts)
    "ceasefire":3, "deal":3, "hormuz":3, "kharg":3, "nuclear":3,
    "ground troops":3, "invasion":3, "brent":3, "oil price":3,
    "rate cut":3, "rate hike":3, "recession":3, "sanctions":3,
    # Impacto ALTO (2 pts)
    "iran":2, "strike":2, "attack":2, "war":2, "conflict":2,
    "israel":2, "houthi":2, "oil":2, "energy":2, "opec":2,
    "trump":2, "fed":2, "inflation":2, "gdp":2, "crisis":2,
    "pakistan":2, "negotiate":2, "talk":2, "peace":2,
    # Impacto MEDIO (1 pt)
    "ukraine":1, "russia":1, "china":1, "taiwan":1, "nato":1,
    "hamas":1, "gaza":1, "hezbollah":1, "missile":1, "market":1,
    "economy":1, "growth":1, "deficit":1, "currency":1, "dollar":1,
}

# Categorias para agrupar el TOP 10
CATEGORIAS = {
    "IRAN / HORMUZ":      ["iran","hormuz","kharg","irgc","khamenei","nuclear","tehran"],
    "DIPLOMACIA":         ["ceasefire","deal","negotiat","talk","peace","pakistan","oman","qatar"],
    "PETROLEO / MACRO":   ["oil","brent","opec","crude","energy","inflation","fed","rate","gdp","recession"],
    "ISRAEL / REGIONES":  ["israel","hamas","gaza","hezbollah","houthi","red sea","lebanon","yemen"],
    "RUSIA / UCRANIA":    ["russia","ukraine","putin","zelensky","nato","kyiv"],
    "GEOPOLITICA GLOBAL": ["china","taiwan","trump","sanctions","g7","dollar","currency"],
}

def _impacto_portfolio(titulo: str) -> str:
    """Retorna una línea de impacto en el portfolio según keywords del título."""
    t = titulo.lower()
    if any(kw in t for kw in ("ceasefire", "deal", "peace", "negotiat", "agreement",
                               "talk", "withdraw", "truce")):
        return "⚠️ <i>Riesgo para NO — vigilar</i>"
    if any(kw in t for kw in ("strike", "attack", "destroy", "bomb", "escalat",
                               "invasion", "ground troops", "hormuz closed")):
        return "✅ <i>Refuerza NO — buena señal</i>"
    if any(kw in t for kw in ("brent", "oil")) and any(kw in t for kw in ("rise", "surge",
                                                                            "jump", "high",
                                                                            "record", "above")):
        return "✅ <i>Brent sube — conflicto activo</i>"
    if any(kw in t for kw in ("brent", "oil")) and any(kw in t for kw in ("fall", "drop",
                                                                            "plunge", "low",
                                                                            "below")):
        return "⚠️ <i>Brent cae — posible distensión</i>"
    return ""

def _score_noticia(titulo: str, fuente_score: int, titulos_vistos: dict,
                   published=None) -> int:
    """Calcula puntuacion 0-20 para priorizar las noticias mas relevantes."""
    t = titulo.lower()
    score = fuente_score  # base: 2-3 pts por fuente

    # Impacto por keywords
    kw_score = 0
    for kw, pts in KEYWORDS_IMPACTO.items():
        if kw in t:
            kw_score += pts
    score += min(kw_score, 8)  # max 8 pts por keywords

    # Bonus si la misma historia aparece en varias fuentes (confirmacion)
    clave = t[:35]
    confirma = titulos_vistos.get(clave, 0)
    score += min(confirma * 2, 4)  # hasta 4 pts por confirmacion cruzada

    # Penalizacion si es muy generico (titulos cortos sin keywords)
    if len(titulo) < 30:
        score -= 2

    # Scoring de frescura (freshness)
    if published is not None:
        import calendar as _cal
        ahora_ts = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        try:
            pub_dt = datetime.datetime(*published[:6])
            diff_h = (ahora_ts - pub_dt).total_seconds() / 3600
            if diff_h < 3:
                score += 3
            elif diff_h < 12:
                score += 2
            elif diff_h < 24:
                score += 1
            else:
                score -= 1
        except Exception:
            pass

    return score

def _categoria_noticia(titulo: str) -> str:
    t = titulo.lower()
    for cat, kws in CATEGORIAS.items():
        if any(k in t for k in kws):
            return cat
    return "GEOPOLITICA GLOBAL"

def enviar_digest_noticias(top_n: int = 10):
    """
    Recoge noticias de fuentes independientes verificadas.
    Aplica scoring anti-sesgo. Selecciona y envia el TOP N (por defecto 10).
    """
    import feedparser
    print(f"Construyendo digest TOP {top_n} anti-sesgo...")

    todas    = []
    vistos   = {}   # titulo[:35] -> cuenta de fuentes que lo mencionan

    for nombre, (url, fscore, em) in FUENTES_RSS.items():
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:25]:
                titulo = e.get("title", "").strip()
                link   = e.get("link", "")
                pub    = e.get("published_parsed")
                if not titulo or len(titulo) < 15:
                    continue
                clave = titulo.lower()[:35]
                vistos[clave] = vistos.get(clave, 0) + 1
                todas.append({
                    "titulo":    titulo,
                    "fuente":    nombre,
                    "fscore":    fscore,
                    "em":        em,
                    "link":      link,
                    "clave":     clave,
                    "published": pub,
                })
        except:
            pass

    # Puntuar y deduplicar
    puntuadas   = []
    claves_usadas = set()
    for n in todas:
        # Descartar si la misma historia ya fue elegida (deduplicacion)
        if n["clave"] in claves_usadas:
            continue
        score = _score_noticia(n["titulo"], n["fscore"], vistos,
                               published=n.get("published"))
        if score <= 0:
            continue
        n["score"]    = score
        n["categoria"] = _categoria_noticia(n["titulo"])
        n["confirma"]  = vistos.get(n["clave"], 1)
        puntuadas.append(n)
        claves_usadas.add(n["clave"])

    # Ordenar por score y tomar TOP N
    puntuadas.sort(key=lambda x: x["score"], reverse=True)
    top10 = puntuadas[:top_n]

    if not top10:
        print("  Sin noticias relevantes encontradas.")
        return

    # Construir mensaje
    ahora = datetime.datetime.now().strftime("%d/%m %H:%M")
    msg   = (f"📰 <b>TOP {top_n} NOTICIAS — {ahora}</b>\n"
             f"<i>Fuentes independientes · anti-sesgo · impacto inversión</i>\n"
             f"{'─'*30}\n\n")

    for i, n in enumerate(top10, 1):
        # Indicador de confirmacion cruzada
        multi = f" ✅<i>x{n['confirma']}</i>" if n["confirma"] >= 2 else ""
        stars = "🔴" if n["score"] >= 10 else ("🟡" if n["score"] >= 7 else "⚪")
        msg  += (f"{stars} <b>#{i} [{n['categoria']}]</b>{multi}\n"
                 f"{n['em']} <i>{n['fuente']}</i> — {n['titulo'][:100]}\n")
        impacto = _impacto_portfolio(n['titulo'])
        if impacto:
            msg += f"   {impacto}\n"
        msg += "\n"

    msg += (f"<i>Evaluadas: {len(todas)} noticias de {len(FUENTES_RSS)} fuentes "
            f"| Excluidas por sesgo: TASS · Xinhua · RT · IRNA</i>")

    # Guardar en log
    hoy  = datetime.datetime.now().strftime("%Y-%m-%d")
    ruta = os.path.join(LOG_DIR, f"noticias_{hoy}.txt")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(f"\n=== TOP {top_n} {ahora} ===\n")
        for n in top10:
            f.write(f"#{n['score']:2} [{n['categoria']}] [{n['fuente']}] {n['titulo']}\n")

    ok = _send(msg)
    print(f"  → TOP {top_n} enviado {'✅' if ok else '❌'} | {len(todas)} evaluadas → {top_n} seleccionadas")

# ==========================================
# SNIPER — GANGAS CORTO PLAZO
# ==========================================
_enviados_sniper = set()

def ejecutar_sniper():
    """Busca contratos con precio >88% que resuelven en <15 días."""
    ahora = datetime.datetime.now()
    print(f"[{ahora.strftime('%H:%M:%S')}] Sniper: buscando gangas <15 días...")
    TEMAS = ["iran", "ceasefire", "oil", "trump", "israel", "ukraine", "hormuz"]
    try:
        r = requests.get(f"{GAMMA_API}/markets?limit=200&active=true&closed=false", timeout=15)
        if r.status_code != 200:
            return
        for m in r.json():
            slug = m.get("slug", "")
            if slug in _enviados_sniper:
                continue
            fecha_str = m.get("endDate") or m.get("endDateIso")
            if not fecha_str:
                continue
            try:
                fecha = datetime.datetime.fromisoformat(str(fecha_str).replace("Z", ""))
                dias  = (fecha - ahora).days
            except:
                continue
            if dias > 15 or dias < 0:
                continue
            titulo = m.get("question", "")
            vol    = float(m.get("volumeNum", 0) or 0)
            if vol < 500_000:
                continue
            if not any(k in titulo.lower() for k in TEMAS):
                continue
            prices = json.loads(m.get("outcomePrices", "[0.5]"))
            for idx, p_str in enumerate(prices):
                p = float(p_str)
                if 0.88 <= p <= 0.96:
                    outcomes = json.loads(m.get("outcomes", '["Yes","No"]'))
                    opcion   = outcomes[idx] if idx < len(outcomes) else "?"
                    _send(
                        f"🏹 <b>SNIPER — GANGA DETECTADA</b>\n\n"
                        f"📋 <b>{titulo}</b>\n"
                        f"💎 Opción: <b>{opcion}</b> al <b>{p:.0%}</b>\n"
                        f"⏳ Cierra en <b>{dias} días</b>\n"
                        f"💰 Volumen: ${vol/1_000_000:.1f}M\n\n"
                        f"🔗 polymarket.com/market/{slug}"
                    )
                    _enviados_sniper.add(slug)
                    print(f"  → Ganga: {titulo[:50]} ({opcion} {p:.0%})")
                    break
    except Exception as e:
        print(f"  [ERROR sniper] {e}")

# ==========================================
# CLI
# ==========================================
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--test" in args:
        _send("✅ <b>telegram_alertas.py funcionando</b>\nTest exitoso.")
        print("Mensaje de prueba enviado.")

    elif "--diario" in args:
        enviar_resumen_diario()
        enviar_digest_noticias(top_n=5)

    elif "--noticias" in args:
        enviar_digest_noticias()

    elif "--check" in args:
        check_rapido()

    elif "--sniper" in args:
        print("Sniper modo continuo — cada hora")
        ejecutar_sniper()
        while True:
            time.sleep(3600)
            ejecutar_sniper()

    else:
        print("Uso: python telegram_alertas.py [--diario | --check | --sniper | --test]")
        print("  --diario  : resumen completo del dia con noticias + portfolio + macro")
        print("  --check   : check rapido de precios, alerta si algo critico")
        print("  --sniper  : modo continuo buscando gangas <15 dias (>88%)")
        print("  --test    : envia mensaje de prueba")
