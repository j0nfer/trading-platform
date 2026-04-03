# -*- coding: utf-8 -*-
"""
watchlist.py — Tracker de Oportunidades Futuras
================================================
Guarda precios base de mercados a vigilar y alerta cuando se mueven >4pp.

CLI:
  python watchlist.py             → muestra estado actual de todos los mercados
  python watchlist.py --update    → actualiza precios base (baseline)
  python watchlist.py --check     → compara vs baseline y envia alertas Telegram
  python watchlist.py --add SLUG  → añade mercado a la watchlist
"""

import os, sys, io, json, requests, datetime
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE    = os.path.dirname(os.path.abspath(__file__))
WL_FILE = os.path.join(BASE, "watchlist.json")
GAMMA   = "https://gamma-api.polymarket.com"

# Watchlist inicial — mercados de oportunidad identificados el 29/03/2026
WATCHLIST_DEFAULT = {
    "us-forces-enter-iran-by-april-30": {
        "nombre": "US Forces enter Iran Apr30",
        "dir_deseada": "YES",
        "precio_base": 0.66,
        "alerta_si_baja_de": 0.55,   # comprar si YES baja a 55% (se abarata)
        "alerta_si_sube_de": 0.80,   # tomar nota si sube más
        "notas": "Ambiguo: verificar si airstrikes cuentan como 'enter'"
    },
    "will-iran-kharg-island-not-under-iranian-control-by-april-30": {
        "nombre": "Kharg Island NO Apr30",
        "dir_deseada": "NO",
        "precio_base": 0.72,
        "alerta_si_baja_de": 0.60,   # oportunidad si NO baja
        "alerta_si_sube_de": 0.88,   # tomar ganancias si NO sube mucho
        "notas": "Zero precedente historico. Score 25/30."
    },
    "iran-leadership-change-by-april-30": {
        "nombre": "Iran Leadership Change NO Apr30",
        "dir_deseada": "NO",
        "precio_base": 0.78,
        "alerta_si_baja_de": 0.65,
        "alerta_si_sube_de": 0.92,
        "notas": "Hard-liner Zolghadr consolidado. Score 25/30."
    },
    "us-x-iran-ceasefire-by-april-30-194-679-389": {
        "nombre": "Ceasefire Apr30 NO",
        "dir_deseada": "NO",
        "precio_base": 0.70,
        "alerta_si_baja_de": 0.58,
        "alerta_si_sube_de": 0.85,
        "notas": "Extension natural de posicion Apr15."
    },
    "us-x-iran-ceasefire-by-may-31": {
        "nombre": "Ceasefire May31 NO",
        "dir_deseada": "NO",
        "precio_base": 0.54,
        "alerta_si_baja_de": 0.42,
        "alerta_si_sube_de": 0.70,
        "notas": "Mercado en zona gris. Esperar señal clara antes de entrar."
    },
}

def _send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML",
                  "disable_web_page_preview": True}, timeout=10)
    except: pass

def _precio_no(slug):
    try:
        r = requests.get(f"{GAMMA}/markets?slug={slug}", timeout=10)
        d = r.json()
        if d:
            prices = json.loads(d[0].get("outcomePrices", "[0.5,0.5]"))
            return round(float(prices[1]) if len(prices) > 1 else 1 - float(prices[0]), 4)
    except: pass
    return None

def cargar_watchlist():
    if os.path.exists(WL_FILE):
        with open(WL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return WATCHLIST_DEFAULT.copy()

def guardar_watchlist(wl):
    with open(WL_FILE, "w", encoding="utf-8") as f:
        json.dump(wl, f, indent=2, ensure_ascii=False)

def mostrar_estado():
    wl = cargar_watchlist()
    ahora = datetime.datetime.now().strftime("%d/%m %H:%M")
    print(f"\n{'='*60}")
    print(f"  WATCHLIST DE OPORTUNIDADES — {ahora}")
    print(f"{'='*60}")
    for slug, m in wl.items():
        p_no = _precio_no(slug)
        if p_no is None:
            print(f"\n  ? {m['nombre']}: precio no disponible")
            continue
        base  = m.get("precio_base", 0.5)
        diff  = p_no - base
        arrow = "^" if diff > 0.02 else ("v" if diff < -0.02 else "->")
        dir_d = m["dir_deseada"]
        # Para YES: precio_yes = 1 - p_no
        if dir_d == "YES":
            p_dir = round(1 - p_no, 4)
            movimiento = "MEJOR" if diff < -0.02 else ("PEOR" if diff > 0.02 else "ESTABLE")
        else:
            p_dir = p_no
            movimiento = "MEJOR" if diff > 0.02 else ("PEOR" if diff < -0.02 else "ESTABLE")
        em = "[OK]" if movimiento == "MEJOR" else ("[!]" if movimiento == "PEOR" else "[=]")
        print(f"\n  {em} {m['nombre']}")
        print(f"     Dir: {dir_d} | Precio actual: {p_dir*100:.0f}c | Base: {base*100:.0f}c {arrow} ({diff*100:+.0f}pp)")
        print(f"     Alerta entrar si baja de: {m['alerta_si_baja_de']*100:.0f}c")
        print(f"     Nota: {m['notas']}")

def actualizar_precios_base():
    """Actualiza precio_base con los precios actuales."""
    wl = cargar_watchlist()
    actualizados = 0
    for slug, m in wl.items():
        p = _precio_no(slug)
        if p:
            wl[slug]["precio_base"] = p
            wl[slug]["ultima_actualizacion"] = datetime.datetime.now().isoformat()[:16]
            actualizados += 1
    guardar_watchlist(wl)
    print(f"  -> {actualizados}/{len(wl)} precios base actualizados")

def check_y_alertar():
    """Compara precios actuales vs baseline. Envía Telegram si hay movimientos relevantes."""
    wl = cargar_watchlist()
    alertas = []
    oportunidades = []

    for slug, m in wl.items():
        p_no = _precio_no(slug)
        if p_no is None:
            continue
        base     = m.get("precio_base", 0.5)
        dir_d    = m["dir_deseada"]
        p_dir    = (1 - p_no) if dir_d == "YES" else p_no
        base_dir = (1 - base) if dir_d == "YES" else base
        diff     = p_dir - base_dir

        alerta_bajo = m.get("alerta_si_baja_de", 0)
        alerta_alto = m.get("alerta_si_sube_de", 1)

        if p_dir <= alerta_bajo:
            oportunidades.append(
                f"<b>{m['nombre']}</b>\n"
                f"   {dir_d} bajo a <b>{p_dir*100:.0f}c</b> (base {base_dir*100:.0f}c)\n"
                f"   -> <b>ZONA DE ENTRADA</b> | {m['notas']}"
            )
        elif p_dir >= alerta_alto:
            alertas.append(
                f"<b>{m['nombre']}</b>\n"
                f"   {dir_d} subio a <b>{p_dir*100:.0f}c</b> (base {base_dir*100:.0f}c)\n"
                f"   -> Posicion ha mejorado +{diff*100:.0f}pp"
            )
        elif abs(diff) >= 0.05:
            alertas.append(
                f"{'↑' if diff > 0 else '↓'} <b>{m['nombre']}</b>: {dir_d} {p_dir*100:.0f}c ({diff*100:+.0f}pp vs base)"
            )

    if oportunidades:
        msg = "<b>WATCHLIST — OPORTUNIDADES DE ENTRADA</b>\n\n" + "\n\n".join(oportunidades)
        _send(msg)
        print(f"  -> {len(oportunidades)} oportunidades de entrada enviadas")

    if alertas:
        msg = "<b>WATCHLIST — MOVIMIENTOS</b>\n\n" + "\n".join(alertas)
        _send(msg)
        print(f"  -> {len(alertas)} movimientos enviados")

    if not oportunidades and not alertas:
        print("  -> Sin movimientos relevantes en watchlist")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--update" in args:
        print("Actualizando precios base...")
        actualizar_precios_base()
    elif "--check" in args:
        print("Checking watchlist vs baseline...")
        check_y_alertar()
    elif "--add" in args:
        idx = args.index("--add")
        if idx + 1 < len(args):
            slug = args[idx + 1]
            wl = cargar_watchlist()
            if slug not in wl:
                p = _precio_no(slug)
                wl[slug] = {
                    "nombre": slug[:50],
                    "dir_deseada": "NO",
                    "precio_base": p or 0.5,
                    "alerta_si_baja_de": round((p or 0.5) - 0.10, 2),
                    "alerta_si_sube_de": round((p or 0.5) + 0.10, 2),
                    "notas": "Anadido manualmente"
                }
                guardar_watchlist(wl)
                print(f"  -> {slug} anadido a watchlist (precio base: {p})")
            else:
                print(f"  -> {slug} ya existe en watchlist")
    else:
        mostrar_estado()
