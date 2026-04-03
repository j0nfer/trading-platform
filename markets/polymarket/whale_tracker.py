"""
whale_tracker.py — Detector de actividad de ballenas en mercados Polymarket

Monitoriza trades grandes en nuestras posiciones para detectar información
privilegiada o señales de mercado antes de que se reflejen en el precio.

Uso:
  python -X utf8 whale_tracker.py               # reporte completo
  python -X utf8 whale_tracker.py --alerta 2000 # umbral alerta en $
  python -X utf8 whale_tracker.py --live         # modo monitor (refresco cada 60s)
  python -X utf8 whale_tracker.py --wallet ADDR  # seguir wallet específica
  python -X utf8 whale_tracker.py --horas 6      # últimas N horas
"""

import sys, os
sys.path.insert(0, "C:\\inversiones")

import argparse
import datetime
import time

from core import (DIRECTORIO, LOGS_DIR, DATA_API, GAMMA_API,
                  SLUG_CEASEFIRE_APR15, SLUG_CONFLICT_JUN30,
                  CONDITION_CEASEFIRE_APR15, CONDITION_CONFLICT_JUN30,
                  fetch_precio, fetch_trades as _fetch_trades,
                  calcular_pnl, dias_restantes, guardar_log,
                  titulo, sep)

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────

POSICIONES = [
    {
        "nombre":      "Ceasefire Apr15",
        "conditionId": CONDITION_CEASEFIRE_APR15,
        "slug":        SLUG_CEASEFIRE_APR15,
        "nuestra_pos": "NO",
        "entrada":     0.657,
        "shares":      304.3,
        "deadline":    "2026-04-15",
    },
    {
        "nombre":      "Conflict Jun30",
        "conditionId": CONDITION_CONFLICT_JUN30,
        "slug":        SLUG_CONFLICT_JUN30,
        "nuestra_pos": "NO",
        "entrada":     0.240,
        "shares":      558.8,
        "deadline":    "2026-06-30",
    },
]

# Wallets conocidas (añadir cuando se identifiquen)
WALLETS_CONOCIDAS = {
    "NOTHINGEVERFRICKINGHAPPENS": "⚠️  Insider documentado — $15K YES ceasefire",
}

UMBRAL_BALLENA_DEFAULT  = 500
UMBRAL_ALERTA_DEFAULT   = 3000
HORAS_DEFAULT           = 24

WALLETS_CONOCIDAS = {
    "NOTHINGEVERFRICKINGHAPPENS": "⚠️  Insider documentado — $15K YES ceasefire",
}

def ts_a_dt(ts: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(ts)

def es_a_favor(outcome: str, side: str, nuestra: str) -> bool:
    """
    Un trade favorece nuestra posición NO si:
      - BUY NO  → sube el precio de NO  → ✅
      - SELL YES → baja el precio de YES → sube NO → ✅
      - BUY YES  → sube YES → baja NO → ❌
      - SELL NO  → baja NO → ❌
    """
    o = outcome.upper()
    s = side.upper()
    n = nuestra.upper()
    if n == "NO":
        return (o == "NO" and s == "BUY") or (o == "YES" and s == "SELL")
    else:  # nuestra pos es YES
        return (o == "YES" and s == "BUY") or (o == "NO" and s == "SELL")

def color_dir(outcome: str, side: str, nuestra: str) -> str:
    return "✅" if es_a_favor(outcome, side, nuestra) else "❌"

def precio_actual(slug: str) -> tuple:
    """Devuelve (yes, no) usando core.fetch_precio."""
    p = fetch_precio(slug)
    if "error" in p:
        return None, None
    return p["yes"], p["no"]


def fetch_trades(conditionId: str, limite: int = 200) -> list:
    """Wrapper de core.fetch_trades."""
    return _fetch_trades(conditionId, limite)


def filtrar_trades(trades: list, horas: int, umbral: float) -> list:
    """Filtra por ventana temporal y tamaño mínimo."""
    corte = datetime.datetime.now() - datetime.timedelta(hours=horas)
    resultado = []
    for t in trades:
        dt = ts_a_dt(t["timestamp"])
        if dt < corte:
            continue
        size = float(t.get("size", 0))
        if size < umbral:
            continue
        resultado.append({**t, "_size": size, "_dt": dt})
    return sorted(resultado, key=lambda x: x["_size"], reverse=True)


# ─── ANÁLISIS ────────────────────────────────────────────────────────────────

def analizar_mercado(pos: dict, horas: int, umbral_ballena: float,
                     umbral_alerta: float) -> dict:
    """Analiza actividad whale en un mercado. Retorna resumen."""
    trades_raw = fetch_trades(pos["conditionId"], limite=300)
    whales     = filtrar_trades(trades_raw, horas, umbral_ballena)
    todos      = filtrar_trades(trades_raw, horas, 0)

    # Totales por dirección
    vol_yes_favor  = sum(t["_size"] for t in todos if t["outcome"].upper() == "YES" and t["side"] == "BUY")
    vol_yes_contra = sum(t["_size"] for t in todos if t["outcome"].upper() == "YES" and t["side"] == "SELL")
    vol_no_favor   = sum(t["_size"] for t in todos if t["outcome"].upper() == "NO"  and t["side"] == "BUY")
    vol_no_contra  = sum(t["_size"] for t in todos if t["outcome"].upper() == "NO"  and t["side"] == "SELL")

    # Volumen neto por outcome (BUY - SELL)
    neto_yes = vol_yes_favor - vol_yes_contra
    neto_no  = vol_no_favor  - vol_no_contra

    # Señal: ¿están las ballenas con nosotros o en contra?
    nuestra_pos = pos["nuestra_pos"].upper()
    vol_con    = sum(t["_size"] for t in whales if es_a_favor(t["outcome"], t["side"], nuestra_pos))
    vol_contra = sum(t["_size"] for t in whales if not es_a_favor(t["outcome"], t["side"], nuestra_pos))

    # Alertas
    alertas = []
    for t in whales:
        if t["_size"] >= umbral_alerta:
            favor = es_a_favor(t["outcome"], t["side"], nuestra_pos)
            alertas.append({
                "size":    t["_size"],
                "outcome": t["outcome"],
                "side":    t["side"],
                "wallet":  t.get("name") or t["proxyWallet"][:16],
                "hora":    t["_dt"].strftime("%H:%M"),
                "favor":   favor,
                "signo":   "✅" if favor else "❌",
            })

    # Wallets conocidas
    conocidas = []
    for t in todos:
        nombre = t.get("name", "")
        if nombre in WALLETS_CONOCIDAS:
            conocidas.append({
                "wallet":  nombre,
                "nota":    WALLETS_CONOCIDAS[nombre],
                "size":    t["_size"],
                "outcome": t["outcome"],
                "hora":    t["_dt"].strftime("%H:%M"),
            })

    # Precio actual usando slug
    yes_p, no_p = precio_actual(pos["slug"])

    return {
        "pos":          pos,
        "yes_p":        yes_p,
        "no_p":         no_p,
        "n_trades":     len(todos),
        "n_whales":     len(whales),
        "vol_yes":      vol_yes_favor,
        "vol_no":       vol_no_favor,
        "neto_yes":     neto_yes,
        "neto_no":      neto_no,
        "vol_con":      vol_con,
        "vol_contra":   vol_contra,
        "whales":       whales[:10],
        "alertas":      alertas,
        "conocidas":    conocidas,
    }


# ─── SEÑAL SMART MONEY ───────────────────────────────────────────────────────

def señal_smart_money(vol_con: float, vol_contra: float) -> str:
    total = vol_con + vol_contra
    if total == 0:
        return "⚪ Sin actividad whale"
    ratio = vol_con / total
    if ratio >= 0.75:
        return "🟢 FUERTE a favor — whales apuestan con nosotros"
    elif ratio >= 0.55:
        return "🟡 MODERADO a favor"
    elif ratio >= 0.45:
        return "⚪ Neutral — divididos"
    elif ratio >= 0.25:
        return "🟠 MODERADO en contra — whales divergen"
    else:
        return "🔴 FUERTE en contra — whales van contra nosotros"


# ─── IMPRIMIR REPORTE ─────────────────────────────────────────────────────────

def imprimir_reporte(resultado: dict, umbral_ballena: float, horas: int):
    pos    = resultado["pos"]
    yes_p  = resultado["yes_p"]
    no_p   = resultado["no_p"]

    titulo(f"WHALE TRACKER — {pos['nombre']}")

    # Precios actuales
    if yes_p and no_p:
        pnl = (no_p - pos["entrada"]) * pos["shares"]
        dias = (datetime.datetime.strptime(pos["deadline"], "%Y-%m-%d").date()
                - datetime.date.today()).days
        print(f"  Precio YES: {yes_p:.1%}  |  NO: {no_p:.1%}  "
              f"|  P/L: {pnl:+.2f}$  |  Días: {dias}")
    sep()

    # Volúmenes
    print(f"  Ventana: últimas {horas}h  |  "
          f"Umbral whale: >${umbral_ballena:,.0f}")
    print(f"  Trades totales: {resultado['n_trades']}  |  "
          f"Whales: {resultado['n_whales']}")
    print()
    print(f"  Volumen BUY   YES: ${resultado['vol_yes']:>10,.2f}   "
          f"NO: ${resultado['vol_no']:>10,.2f}")
    print(f"  Neto (B-S)    YES: ${resultado['neto_yes']:>+10,.2f}   "
          f"NO: ${resultado['neto_no']:>+10,.2f}")

    sep()

    # Señal smart money
    nuestra = pos["nuestra_pos"]
    vol_con    = resultado["vol_con"]
    vol_contra = resultado["vol_contra"]
    señal = señal_smart_money(vol_con, vol_contra)
    print(f"\n  SEÑAL SMART MONEY [{nuestra}]:")
    print(f"  {señal}")
    print(f"  Con nosotros: ${vol_con:,.2f}   En contra: ${vol_contra:,.2f}")

    # Top whales
    if resultado["whales"]:
        print(f"\n  TOP WHALES (>${umbral_ballena:,.0f}) — últimas {horas}h:")
        for i, t in enumerate(resultado["whales"][:8], 1):
            signo = color_dir(t["outcome"], t["side"], nuestra)
            wallet = (t.get("name") or t["proxyWallet"][:14]).ljust(20)
            print(f"  {i:2}. {signo} {wallet}  "
                  f"{t['side']:4} {t['outcome']:3}  "
                  f"${t['_size']:>9,.2f}  @ {t['price']:.3f}  "
                  f"{t['_dt'].strftime('%H:%M')}")

    # Alertas grandes
    if resultado["alertas"]:
        print()
        sep("!", 62)
        print(f"  ALERTAS — TRADES GRANDES:")
        for a in resultado["alertas"]:
            direc = "A FAVOR ✅" if a["favor"] else "EN CONTRA ❌"
            print(f"  ${a['size']:,.2f}  {a['outcome']} {a['side']}  "
                  f"{direc}  wallet: {a['wallet']}  {a['hora']}")
        sep("!", 62)

    # Wallets conocidas
    if resultado["conocidas"]:
        print(f"\n  WALLETS CONOCIDAS ACTIVAS:")
        for k in resultado["conocidas"]:
            print(f"  ⚠️  {k['wallet']}: ${k['size']:.2f} {k['outcome']} "
                  f"a las {k['hora']}")
            print(f"      → {k['nota']}")


# ─── MODO LIVE ───────────────────────────────────────────────────────────────

def modo_live(args):
    intervalo = 60
    print(f"\n  MODO LIVE — refresco cada {intervalo}s  (Ctrl+C para salir)\n")
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print(f"  Actualizado: {datetime.datetime.now().strftime('%H:%M:%S')}")
            for pos in POSICIONES:
                res = analizar_mercado(pos, args.horas, args.alerta / 2, args.alerta)
                imprimir_reporte(res, args.alerta / 2, args.horas)
            print(f"\n  Próximo refresco en {intervalo}s...")
            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\n  Monitor detenido.")


# ─── GUARDAR LOG ─────────────────────────────────────────────────────────────

def guardar_log_whales(resultados: list):
    entrada = {"mercados": [
        {"nombre":     r["pos"]["nombre"],
         "yes_p":      r["yes_p"], "no_p": r["no_p"],
         "vol_con":    r["vol_con"], "vol_contra": r["vol_contra"],
         "n_whales":   r["n_whales"], "alertas": r["alertas"]}
        for r in resultados
    ]}
    ruta = guardar_log("whales", entrada)
    print(f"\n  Log guardado: {ruta}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Whale tracker Polymarket")
    parser.add_argument("--alerta",  type=float, default=UMBRAL_ALERTA_DEFAULT,
                        help=f"Umbral alerta en $ (default: {UMBRAL_ALERTA_DEFAULT})")
    parser.add_argument("--umbral",  type=float, default=UMBRAL_BALLENA_DEFAULT,
                        help=f"Umbral whale en $ (default: {UMBRAL_BALLENA_DEFAULT})")
    parser.add_argument("--horas",   type=int,   default=HORAS_DEFAULT,
                        help=f"Ventana temporal en horas (default: {HORAS_DEFAULT})")
    parser.add_argument("--live",    action="store_true", help="Modo monitor continuo")
    parser.add_argument("--wallet",  type=str,   default=None,
                        help="Filtrar por wallet o nombre")
    parser.add_argument("--log",     action="store_true", help="Guardar log en JSON")
    args = parser.parse_args()

    if args.live:
        modo_live(args)
        return

    print(f"\n{'='*62}")
    print(f"  WHALE TRACKER — {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Umbral whale: >${args.umbral:,.0f}  |  Alerta: >${args.alerta:,.0f}  "
          f"|  Ventana: {args.horas}h")
    print(f"{'='*62}")

    resultados = []
    for pos in POSICIONES:
        res = analizar_mercado(pos, args.horas, args.umbral, args.alerta)

        # Filtro por wallet si se especifica
        if args.wallet:
            wallet_lower = args.wallet.lower()
            res["whales"] = [
                t for t in res["whales"]
                if wallet_lower in (t.get("name") or "").lower()
                or wallet_lower in t["proxyWallet"].lower()
            ]

        imprimir_reporte(res, args.umbral, args.horas)
        resultados.append(res)

    # Resumen ejecutivo
    titulo("RESUMEN EJECUTIVO")
    alertas_totales = sum(len(r["alertas"]) for r in resultados)
    for r in resultados:
        señal = señal_smart_money(r["vol_con"], r["vol_contra"])
        no_p  = r["no_p"] or 0
        pnl   = (no_p - r["pos"]["entrada"]) * r["pos"]["shares"]
        print(f"  {r['pos']['nombre']:20}  P/L: {pnl:+7.2f}$  |  {señal}")

    if alertas_totales > 0:
        print(f"\n  ⚠️  {alertas_totales} trades grandes detectados — revisar arriba")

    if args.log:
        guardar_log_whales(resultados)


if __name__ == "__main__":
    main()
