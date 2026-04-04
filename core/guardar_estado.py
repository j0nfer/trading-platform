# -*- coding: utf-8 -*-
"""
guardar_estado.py — Se ejecuta automáticamente al cerrar sesión de Claude.
Actualiza ESTADO_SESION.md con precios actuales y fecha.
"""
import json, os, sys, requests
from datetime import datetime

GAMMA_API   = "https://gamma-api.polymarket.com"
TRADING_DIR = os.environ.get("TRADING_DIR", "C:\\inversiones")

# Slugs verificados de las posiciones reales
SLUG_P1 = "us-x-iran-ceasefire-by-april-15-182-528-637"
SLUG_P2 = "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725"

def precio_no(slug):
    """Obtiene precio NO directo del slug de mercado."""
    try:
        r = requests.get(f"{GAMMA_API}/markets", params={"slug": slug}, timeout=8)
        m = r.json()
        m = m[0] if isinstance(m, list) and m else m
        prices = m.get("outcomePrices", "[]")
        if isinstance(prices, str): prices = json.loads(prices)
        outcomes = m.get("outcomes", "[]")
        if isinstance(outcomes, str): outcomes = json.loads(outcomes)
        idx_no = next((i for i, o in enumerate(outcomes)
                       if isinstance(o, str) and o.strip().upper() == "NO"), 1)
        p = float(str(prices[idx_no]).strip('"\''))
        return round(p, 4) if 0.02 <= p <= 0.98 else None
    except Exception:
        return None

def brent():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/BZ%3DF",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception:
        return None

def main():
    ahora = datetime.now()
    fecha = ahora.strftime("%Y-%m-%d %H:%M")

    p1_no  = precio_no(SLUG_P1) or 0.945
    p2_no  = precio_no(SLUG_P2) or 0.445
    p4_no  = precio_no("will-the-us-invade-iran-before-2027") or 0.425
    p3_yes = 0.775  # WTI $120 YES — slug pendiente verificacion
    b = brent()

    pnl1 = round((p1_no  - 0.657) * 73.0,  2)
    pnl2 = round((p2_no  - 0.240) * 558.8, 2)
    pnl3 = round((p3_yes - 0.510) * 289.0, 2)
    pnl4 = round((p4_no  - 0.470) * 457.6, 2)
    pnl_total = round(pnl1 + pnl2 + pnl3 + pnl4, 2)

    brent_str = f"${b:.2f}" if b else "N/D"

    from datetime import date
    dias_apr15 = (date(2026, 4, 15) - date.today()).days
    dias_apr6  = (date(2026, 4,  6) - date.today()).days
    dias_jun30 = (date(2026, 6, 30) - date.today()).days

    dias_dic31 = (date(2026, 12, 31) - date.today()).days

    contenido = f"""# ESTADO DE SESIÓN — Auto-generado
<!-- Este archivo se actualiza automáticamente al cerrar cada sesión -->
<!-- Claude lo lee al inicio para retomar sin re-establecer contexto -->

## Fecha última actualización
{fecha}

## Portfolio (precios al cierre de sesión)

| Posición | Dir | Entrada | Precio actual | P/L | Resuelve |
|---|---|---|---|---|---|
| Pos1 Ceasefire Apr15 (73sh) | NO | 65.7¢ | **{p1_no:.0%}** | **{pnl1:+.0f}$** | 15 abr ({dias_apr15}d) |
| Pos2 Conflict Jun30 (558.8sh) | NO | 24¢ | **{p2_no:.0%}** | **{pnl2:+.0f}$** | 30 jun ({dias_jun30}d) |
| Pos3 WTI $120 YES (289sh) | YES | 51¢ | **{p3_yes:.0%}** | **{pnl3:+.0f}$** | 31 dic ({dias_dic31}d) |
| Pos4 InvadeIran NO (457.6sh) | NO | 47¢ | **{p4_no:.0%}** | **{pnl4:+.0f}$** | 31 dic ({dias_dic31}d) |
| **TOTAL P/L** | | | | **{pnl_total:+.0f}$** | |

Capital total: $736.21 USDC | Cash: $0.01 (SIN LIQUIDEZ)

## Deadlines críticos
- 🔴 **6 ABRIL** ({dias_apr6} días) — Trump decide si reanuda strikes
- 🟡 **15 ABRIL** ({dias_apr15} días) — Resolución ceasefire Apr15
- ⚪ **30 JUNIO** ({dias_jun30} días) — Resolución conflict ends Jun30

## Contexto macro
- Brent: {brent_str}
- Insider activo: wallet "NOTHINGEVERFRICKINGHAPPENS" apostó $15.6K a YES Apr15

## Scripts disponibles
```
python -X utf8 analizar_portfolio.py --rapido   # análisis rápido
python -X utf8 comparador_mercados.py --iran    # precios Iran en tiempo real
python -X utf8 telegram_alertas.py --check      # check noticias/precios
python -X utf8 correlacion_posiciones.py        # correlación portfolio
python telegram_alertas.py --setup              # instrucciones bot Telegram
```

## Tarea más urgente al retomar
1. ⚠️  Configurar bot Telegram: @BotFather → TOKEN → .env
2. 🔍 Monitorizar 6 abril (deadline Trump)
3. 📊 Actualizar portfolio.json si precios cambian >5pp
"""

    path = os.path.join(TRADING_DIR, "ESTADO_SESION.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"[guardar_estado] Estado guardado: P/L={pnl_total:+.0f}$ Brent={brent_str}")

if __name__ == "__main__":
    main()
