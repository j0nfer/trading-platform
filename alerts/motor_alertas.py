# -*- coding: utf-8 -*-
"""
motor_alertas.py — Motor de Inteligencia para Nuevas Apuestas
=============================================================
Combina 4 sistemas:
  1. Scanner de mercados Polymarket (con scoring 0-100)
  2. Detector de divergencias macro (Brent / VIX / Gold vs precios)
  3. Whale Tracker (trades grandes en mercados geopoliticos)
  4. Indice Fear & Greed Geopolitico propio

CLI:
  python motor_alertas.py --scan         → escanea y muestra top oportunidades
  python motor_alertas.py --whales       → ultimos movimientos grandes
  python motor_alertas.py --macro        → divergencias macro actuales
  python motor_alertas.py --fear         → indice Fear & Greed geopolitico
  python motor_alertas.py --test         → una pasada completa con Telegram
  python motor_alertas.py               → modo continuo cada 30 min
"""

import sys, os
sys.path.insert(0, "C:\\inversiones")

import io, json, time, requests, yfinance as yf, schedule
from datetime import datetime, date, timezone
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ==========================================
# CONFIGURACION
# ==========================================
KEYWORDS_GEO = [
    "iran", "israel", "ceasefire", "nuclear", "hormuz", "war", "strike",
    "sanctions", "conflict", "regime", "attack", "deal", "tregua",
    "russia", "ukraine", "china", "taiwan", "oil", "brent", "opec",
    "trump", "netanyahu", "khamenei", "hezbollah", "hamas", "houthi"
]

WALLETS_VIP = {
    "NOTHINGEVERFRICKINGHAPPENS": None,   # se busca por pseudonym
}

MIN_VOLUMEN   = 20_000   # liquidez minima — mercados serios
MIN_SCORE     = 80       # score minimo para enviar alerta (era 45)
WHALE_USD     = 3_000    # trade >= $3000 = ballena real (era 1000)
WHALE_USD_MED = 1_500    # trade >= $1500 = movimiento notable (era 300)
COOLDOWN_H    = 24       # una sola alerta por mercado al dia (era 4h)
MAX_OPOR_DIA  = 2        # maximo 2 oportunidades por dia en total

# Memoria para no repetir alertas
_alertas_enviadas  = {}   # slug -> timestamp ultima alerta
_opor_enviadas_hoy = 0    # contador de oportunidades enviadas hoy
_fecha_contador    = None # fecha del contador

# ==========================================
# 1. TELEGRAM
# ==========================================
def telegram(msg: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg,
                                  "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"[Telegram ERROR] {e}")

def _ya_enviado(slug: str) -> bool:
    """Evita spam: mismo mercado max 1 alerta cada COOLDOWN_H horas"""
    if slug not in _alertas_enviadas:
        return False
    horas = (datetime.now() - _alertas_enviadas[slug]).total_seconds() / 3600
    return horas < COOLDOWN_H

def _marcar_enviado(slug: str):
    _alertas_enviadas[slug] = datetime.now()

def _cupo_oportunidades() -> bool:
    """Devuelve True si aun hay cupo de oportunidades para hoy"""
    global _opor_enviadas_hoy, _fecha_contador
    hoy = date.today()
    if _fecha_contador != hoy:
        _opor_enviadas_hoy = 0
        _fecha_contador = hoy
    return _opor_enviadas_hoy < MAX_OPOR_DIA

def _consumir_cupo():
    global _opor_enviadas_hoy
    _opor_enviadas_hoy += 1

# ==========================================
# 2. SCANNER Y SCORER DE MERCADOS
# ==========================================
def _precio_no(mercado: dict) -> float:
    try:
        prices = json.loads(mercado.get("outcomePrices", "[0.5,0.5]"))
        if len(prices) >= 2:
            return float(prices[1])
        return 1 - float(prices[0])
    except:
        return 0.5

def _dias_hasta(mercado: dict):
    for campo in ["endDate", "endDateIso", "end_date"]:
        val = mercado.get(campo)
        if val:
            try:
                if "T" in str(val):
                    fecha = datetime.fromisoformat(str(val).replace("Z","")).date()
                else:
                    fecha = date.fromisoformat(str(val)[:10])
                return (fecha - date.today()).days
            except:
                continue
    return None

def calcular_score(mercado: dict):
    """
    Puntuacion 0-100 para un mercado de Polymarket.
    Devuelve (score, razones, p_yes, p_no, dias)
    """
    score   = 0
    razones = []

    # -- Liquidez (0-30 pts) --
    vol = float(mercado.get("volumeNum", 0) or 0)
    if   vol >= 200_000: score += 30; razones.append(f"Liquidez alta ${vol/1000:.0f}K")
    elif vol >=  50_000: score += 22; razones.append(f"Liquidez buena ${vol/1000:.0f}K")
    elif vol >=  10_000: score += 14; razones.append(f"Liquidez media ${vol/1000:.0f}K")
    elif vol >=   5_000: score +=  7; razones.append(f"Liquidez baja ${vol/1000:.0f}K")
    else:
        return None   # descartado por falta de liquidez

    p_no  = _precio_no(mercado)
    p_yes = 1 - p_no

    # -- Precio: zonas de oportunidad (0-30 pts) --
    # Zona de valor: 10-35% o 65-90% (opinion formada pero incertidumbre real)
    if   0.10 <= p_no <= 0.35 or 0.65 <= p_no <= 0.90:
        score += 30; razones.append(f"Zona valor: NO={p_no*100:.0f}%")
    elif 0.35 <  p_no <= 0.48 or 0.52 <= p_no <  0.65:
        score += 12; razones.append(f"Zona neutral: NO={p_no*100:.0f}%")
    elif p_no < 0.05 or p_no > 0.95:
        score +=  5; razones.append(f"Precio casi resuelto: NO={p_no*100:.0f}%")
    else:
        score +=  8; razones.append(f"Precio: NO={p_no*100:.0f}%")

    # -- Tiempo a resolucion (0-25 pts) --
    dias = _dias_hasta(mercado)
    if dias is not None:
        if   5 <= dias <=  45: score += 25; razones.append(f"Sweet spot: {dias}d para resolver")
        elif 3 <= dias <   5:  score += 18; razones.append(f"Urgente: {dias}d")
        elif 45 < dias <= 120: score += 15; razones.append(f"Medio plazo: {dias}d")
        elif dias > 120:       score +=  5; razones.append(f"Largo plazo: {dias}d")
        elif dias <  0:
            return None   # ya resuelto
    else:
        dias = None

    # -- Keywords criticas (0-15 pts) --
    texto = (mercado.get("question","") + " " +
             mercado.get("description","")).lower()
    alta_prio = ["iran","nuclear","ceasefire","hormuz","strike","attack","war"]
    hits_alta = [w for w in alta_prio if w in texto]
    hits_gen  = [w for w in KEYWORDS_GEO if w in texto and w not in hits_alta]
    if hits_alta:
        score += 15; razones.append(f"Keywords prioritarias: {', '.join(hits_alta[:3])}")
    elif hits_gen:
        score +=  7; razones.append(f"Keywords geo: {', '.join(hits_gen[:3])}")

    return score, razones, p_yes, p_no, dias

def scan_mercados(verbose: bool = False) -> list:
    """Escanea los primeros 500 mercados activos y devuelve top oportunidades."""
    print("🔍 Escaneando mercados Polymarket...")
    oportunidades = []
    total_revisados = 0

    for offset in range(0, 500, 100):
        try:
            url = (f"https://gamma-api.polymarket.com/markets"
                   f"?active=true&closed=false&limit=100&offset={offset}"
                   f"&order=volumeNum&ascending=false")
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                break
            mercados = r.json()
            if not mercados:
                break

            for m in mercados:
                total_revisados += 1
                question = (m.get("question","") + " " +
                            m.get("description","")).lower()
                if not any(k in question for k in KEYWORDS_GEO):
                    continue

                res = calcular_score(m)
                if res is None:
                    continue
                score, razones, p_yes, p_no, dias = res

                if score >= MIN_SCORE:
                    oportunidades.append({
                        "question": m.get("question","Sin titulo"),
                        "slug":     m.get("slug",""),
                        "score":    score,
                        "razones":  razones,
                        "p_yes":    p_yes,
                        "p_no":     p_no,
                        "dias":     dias,
                        "volumen":  float(m.get("volumeNum", 0) or 0),
                    })
        except Exception as e:
            print(f"  [WARN] offset {offset}: {e}")
            break

    oportunidades.sort(key=lambda x: x["score"], reverse=True)
    print(f"  → Revisados: {total_revisados} | Oportunidades score>={MIN_SCORE}: {len(oportunidades)}")
    return oportunidades[:10]

# ==========================================
# 3. DIVERGENCIAS MACRO
# ==========================================
def check_divergencias() -> tuple:
    """
    Compara indicadores macro (Brent, VIX, Gold) con precios de Polymarket.
    Devuelve (lista_alertas, dict_datos_macro)
    """
    print("📊 Verificando divergencias macro...")
    alertas = []
    macro   = {}

    # -- Obtener datos macro --
    tickers = {"brent": "BZ=F", "vix": "^VIX", "gold": "GC=F", "dxy": "DX-Y.NYB"}
    for nombre, ticker in tickers.items():
        try:
            macro[nombre] = yf.Ticker(ticker).fast_info["last_price"]
        except:
            macro[nombre] = None

    # -- Precio ceasefire Apr15 --
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/markets"
            "?slug=us-x-iran-ceasefire-by-april-15-182-528-637",
            timeout=10)
        d = r.json()
        if d:
            prices = json.loads(d[0].get("outcomePrices","[0.18,0.82]"))
            macro["ceasefire_yes"] = float(prices[0])
        else:
            macro["ceasefire_yes"] = 0.18
    except:
        macro["ceasefire_yes"] = 0.18

    b   = macro.get("brent")
    v   = macro.get("vix")
    g   = macro.get("gold")
    c_y = macro.get("ceasefire_yes", 0.18)

    if b and v:
        # Tension alta pero mercado infravalora riesgo
        if b > 95 and v > 22 and c_y > 0.28:
            alertas.append(
                f"⚡ <b>DIVERGENCIA TENSION:</b> Brent=${b:.0f} + VIX={v:.1f} "
                f"pero ceasefire YES={c_y*100:.0f}% — mercado sobrevalora paz → refuerza NO")

        # Brent cayendo = mercado descuenta tregua
        if b < 85 and c_y < 0.20:
            alertas.append(
                f"⚡ <b>DIVERGENCIA BRENT:</b> Brent=${b:.0f} (bajo) "
                f"pero ceasefire YES={c_y*100:.0f}% — posible desfase → vigilar YES")

        # Gold sube fuerte = risk-off, conflicto se alarga
        if g and g > 3000 and c_y > 0.25:
            alertas.append(
                f"⚡ <b>DIVERGENCIA GOLD:</b> Oro=${g:.0f} (risk-off) "
                f"pero ceasefire YES={c_y*100:.0f}% — inconsistente → favorece NO")

    return alertas, macro

# ==========================================
# 4. WHALE TRACKER
# ==========================================
def check_whales() -> list:
    """
    Detecta trades grandes (>$300) en mercados geopoliticos recientes.
    Prioriza wallets conocidas (NOTHINGEVERFRICKINGHAPPENS).
    """
    print("🐳 Rastreando ballenas...")
    hallazgos = []

    try:
        # Traemos los 200 trades mas recientes y filtramos
        url = "https://data-api.polymarket.com/trades?limit=200"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []
        trades = r.json()

        for t in trades:
            size  = float(t.get("size", 0) or 0)
            title = (t.get("title","") or "").lower()
            pseudo = t.get("pseudonym","") or ""
            wallet = t.get("proxyWallet","") or ""

            # Filtrar por tamano minimo
            if size < WHALE_USD_MED:
                continue

            # Filtrar por relevancia geo O wallet VIP
            es_geo = any(k in title for k in KEYWORDS_GEO)
            es_vip = any(vip.lower() in pseudo.lower() for vip in WALLETS_VIP)

            if not es_geo and not es_vip:
                continue

            hallazgos.append({
                "size":    size,
                "title":   t.get("title","")[:60],
                "slug":    t.get("slug",""),
                "side":    t.get("side",""),
                "outcome": t.get("outcome",""),
                "wallet":  pseudo if pseudo else wallet[:14],
                "es_vip":  es_vip,
            })

    except Exception as e:
        print(f"  [WARN] Whale API: {e}")

    hallazgos.sort(key=lambda x: x["size"], reverse=True)
    print(f"  → {len(hallazgos)} movimientos grandes detectados")
    return hallazgos[:8]

# ==========================================
# 5. FEAR & GREED GEOPOLITICO
# ==========================================
def calcular_fear_greed(macro: dict) -> tuple:
    """
    Indice propio 0-100:
    0-20  = Euforia (mercado descuenta paz total)
    21-40 = Calma
    41-60 = Incertidumbre
    61-80 = Tension
    81-100= Miedo extremo (guerra inminente)
    Devuelve (valor, etiqueta, emoji)
    """
    score = 50  # base

    b = macro.get("brent")
    v = macro.get("vix")
    g = macro.get("gold")
    c = macro.get("ceasefire_yes", 0.18)

    if b:
        if   b > 110: score += 20
        elif b >  95: score += 10
        elif b <  75: score -= 15
        elif b <  85: score -=  5

    if v:
        if   v > 30: score += 15
        elif v > 22: score +=  8
        elif v < 15: score -= 10

    if g:
        if   g > 3100: score += 10
        elif g > 2800: score +=  5
        elif g < 2400: score -=  8

    # Ceasefire price (YES alto = mercado en calma)
    score -= int(c * 40)   # si c=0.5 → -20; si c=0.1 → -4; si c=0.8 → -32

    score = max(0, min(100, score))

    if   score >= 80: etiqueta, emoji = "MIEDO EXTREMO",   "🔴"
    elif score >= 60: etiqueta, emoji = "TENSION",         "🟠"
    elif score >= 40: etiqueta, emoji = "INCERTIDUMBRE",   "🟡"
    elif score >= 20: etiqueta, emoji = "CALMA",           "🟢"
    else:             etiqueta, emoji = "EUFORIA (RIESGO)","⚪"

    return score, etiqueta, emoji

# ==========================================
# 6. COMPOSICION DE ALERTAS
# ==========================================
def _alerta_oportunidad(op: dict) -> str:
    estrellas = "⭐" * max(1, op["score"] // 20)
    if op["p_no"] > 0.58:
        dir_str = f"NO  ({op['p_no']*100:.0f}¢)"
    elif op["p_yes"] > 0.58:
        dir_str = f"YES ({op['p_yes']*100:.0f}¢)"
    else:
        dir_str = f"NEUTRAL (YES {op['p_yes']*100:.0f}% / NO {op['p_no']*100:.0f}%)"

    msg  = f"🎯 <b>OPORTUNIDAD DETECTADA — {op['score']}/100</b> {estrellas}\n\n"
    msg += f"📋 <b>{op['question'][:90]}</b>\n\n"
    msg += f"💡 Direccion: <b>{dir_str}</b>\n"
    if op["dias"] is not None:
        msg += f"⏰ Resuelve en <b>{op['dias']} dias</b>\n"
    msg += f"💰 Volumen: ${op['volumen']/1000:.1f}K\n\n"
    msg += "📊 <b>Por que:</b>\n"
    for r in op["razones"]:
        msg += f"  • {r}\n"
    if op["slug"]:
        msg += f"\n🔗 polymarket.com/event/{op['slug']}"
    return msg

def _alerta_whale(hallazgos: list) -> str:
    msg  = "🐳 <b>MOVIMIENTO BALLENA — Polymarket</b>\n"
    msg += f"<i>{datetime.now().strftime('%H:%M')} · {len(hallazgos)} trades grandes</i>\n\n"
    for h in hallazgos[:5]:
        prefijo = "⭐ VIP " if h["es_vip"] else ""
        msg += f"{prefijo}💵 <b>${h['size']:.0f}</b> {h['side'].upper()} <b>{h['outcome']}</b>\n"
        msg += f"   📋 {h['title']}\n"
        msg += f"   👤 {h['wallet']}\n\n"
    return msg

def _alerta_macro(macro: dict, divergencias: list, fg_score: int, fg_etiq: str, fg_emoji: str) -> str:
    b = macro.get("brent"); v = macro.get("vix")
    g = macro.get("gold");  d = macro.get("dxy")
    c = macro.get("ceasefire_yes", 0.18)

    msg  = f"📊 <b>RESUMEN MACRO — {datetime.now().strftime('%H:%M')}</b>\n\n"
    msg += f"{fg_emoji} <b>Fear & Greed Geopolitico: {fg_score}/100 — {fg_etiq}</b>\n\n"
    if b: msg += f"⛽ Brent: <b>${b:.2f}</b>\n"
    if v: msg += f"📉 VIX:   <b>{v:.1f}</b>\n"
    if g: msg += f"🥇 Gold:  <b>${g:.0f}</b>\n"
    if d: msg += f"💵 DXY:   <b>{d:.2f}</b>\n"
    msg += f"🎲 Ceasefire YES: <b>{c*100:.0f}%</b>\n"

    if divergencias:
        msg += "\n⚡ <b>Divergencias detectadas:</b>\n"
        for dv in divergencias:
            msg += f"  {dv}\n"
    return msg

# ==========================================
# 7. MOTOR PRINCIPAL
# ==========================================
def run_motor(modo_silencioso: bool = False) -> dict:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"  MOTOR ALERTAS — {ts}")
    print(f"{'='*55}")

    resultado = {"oportunidades": 0, "whales": 0, "divergencias": 0}

    # --- 1. Macro + Fear & Greed ---
    divs, macro = check_divergencias()
    fg_score, fg_etiq, fg_emoji = calcular_fear_greed(macro)
    print(f"  Fear & Greed: {fg_score}/100 — {fg_etiq}")

    if divs:
        alerta_m = _alerta_macro(macro, divs, fg_score, fg_etiq, fg_emoji)
        if not modo_silencioso:
            telegram(alerta_m)
        resultado["divergencias"] = len(divs)
        print(f"  → {len(divs)} divergencias macro enviadas")

    # --- 2. Scanner de oportunidades (max MAX_OPOR_DIA por dia) ---
    oportunidades = scan_mercados()
    enviadas = 0
    for op in oportunidades:
        if not _cupo_oportunidades():
            print(f"  [LIMITE DIARIO] Ya se enviaron {MAX_OPOR_DIA} oportunidades hoy")
            break
        if _ya_enviado(op["slug"]):
            print(f"  [SKIP cooldown] {op['question'][:40]}")
            continue
        # Filtro extra: solo si el score es realmente alto
        if op["score"] < MIN_SCORE:
            break
        msg = _alerta_oportunidad(op)
        if not modo_silencioso:
            telegram(msg)
            time.sleep(1.5)
        _marcar_enviado(op["slug"])
        _consumir_cupo()
        enviadas += 1
        print(f"  ✅ Score {op['score']}: {op['question'][:45]}...")
    resultado["oportunidades"] = enviadas

    # --- 3. Whale Tracker (solo ballenas grandes) ---
    hallazgos = check_whales()
    ballenas_grandes = [h for h in hallazgos if h["size"] >= WHALE_USD]
    if ballenas_grandes:
        slug_ballena = "whale_" + ballenas_grandes[0]["slug"]
        if not _ya_enviado(slug_ballena):
            msg_w = _alerta_whale(ballenas_grandes)
            if not modo_silencioso:
                telegram(msg_w)
            _marcar_enviado(slug_ballena)
            resultado["whales"] = len(ballenas_grandes)

    print(f"\n  RESUMEN: {enviadas} oportunidades | "
          f"{len(hallazgos)} whales | {len(divs)} divergencias")
    print(f"{'='*55}\n")
    return resultado

# ==========================================
# 8. CLI
# ==========================================
def _print_scan():
    ops = scan_mercados(verbose=True)
    if not ops:
        print("Sin oportunidades por encima del umbral.")
        return
    print(f"\n{'─'*60}")
    print(f"  TOP OPORTUNIDADES GEOPOLITICAS ({len(ops)} mercados)")
    print(f"{'─'*60}")
    for i, op in enumerate(ops, 1):
        dir_s = "NO " if op["p_no"] > 0.58 else "YES" if op["p_yes"] > 0.58 else "---"
        dias_s = f"{op['dias']}d" if op["dias"] is not None else "?"
        print(f"\n{i:2}. [{op['score']:3}/100] {dir_s}  Vol=${op['volumen']/1000:.0f}K  Res:{dias_s}")
        print(f"    {op['question'][:70]}")
        for r in op["razones"]:
            print(f"      • {r}")

def _print_whales():
    ws = check_whales()
    if not ws:
        print("Sin movimientos grandes detectados.")
        return
    print(f"\n{'─'*60}")
    print(f"  WHALE TRACKER — {len(ws)} movimientos grandes")
    print(f"{'─'*60}")
    for w in ws:
        vip = " ⭐VIP" if w["es_vip"] else ""
        print(f"  ${w['size']:7.0f} | {w['side']:4} {w['outcome'][:10]:12} | "
              f"{w['title'][:40]:40} | {w['wallet']}{vip}")

def _print_macro():
    divs, macro = check_divergencias()
    fg_s, fg_e, fg_em = calcular_fear_greed(macro)
    print(f"\n{'─'*60}")
    print(f"  MACRO GEOPOLITICO — Fear & Greed: {fg_s}/100 {fg_em} {fg_e}")
    print(f"{'─'*60}")
    for k, v in macro.items():
        if v is not None:
            print(f"  {k:20}: {v:.2f}" if isinstance(v, float) else f"  {k:20}: {v}")
    if divs:
        print("\n  DIVERGENCIAS:")
        for d in divs:
            print(f"  {d}")
    else:
        print("\n  Sin divergencias significativas.")

def _print_fear():
    _, macro = check_divergencias()
    s, e, em = calcular_fear_greed(macro)
    barra = "█" * (s // 5) + "░" * (20 - s // 5)
    print(f"\n  {em} Fear & Greed Geopolitico")
    print(f"  [{barra}] {s}/100")
    print(f"  Estado: {e}")
    b = macro.get("brent"); v = macro.get("vix"); c = macro.get("ceasefire_yes",0.18)
    if b: print(f"  Brent: ${b:.1f}")
    if v: print(f"  VIX:   {v:.1f}")
    print(f"  Ceasefire YES: {c*100:.0f}%")


if __name__ == "__main__":
    if "--scan"   in sys.argv: _print_scan()
    elif "--whales"in sys.argv: _print_whales()
    elif "--macro" in sys.argv: _print_macro()
    elif "--fear"  in sys.argv: _print_fear()
    elif "--test"  in sys.argv:
        print("TEST completo — enviando alertas reales a Telegram...")
        run_motor(modo_silencioso=False)
    else:
        # Modo continuo: cada 30 minutos
        print("🚀 Motor de Alertas iniciado — ciclo cada 30 minutos")
        telegram(
            "🧠 <b>Motor de Inteligencia Activado</b>\n"
            "Escaneando:\n"
            "  • Mercados Polymarket (scoring 0-100)\n"
            "  • Divergencias macro (Brent/VIX/Gold)\n"
            "  • Whale Tracker (trades >$300)\n"
            "  • Fear & Greed Geopolitico\n"
            "Frecuencia: cada 30 minutos"
        )
        run_motor()
        schedule.every(2).hours.do(run_motor)
        while True:
            schedule.run_pending()
            time.sleep(60)
