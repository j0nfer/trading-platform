"""
monitor_precios.py
Monitor de precios: SNDK (alerta entrada $580-620) + WTI/Brent en tiempo real.
"""
import sys
import json
import requests
import yfinance as yf
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"

# Configuracion SNDK
SNDK_TICKER      = "SNDK"
SNDK_ZONA_MIN    = 580
SNDK_ZONA_MAX    = 620
SNDK_CONSENSO    = 555
SNDK_BETA        = 2.74
SNDK_EARNINGS    = "2026-05-13"

# Tickers petroleo en yfinance
WTI_TICKER   = "CL=F"    # WTI Crude Futures
BRENT_TICKER = "BZ=F"    # Brent Crude Futures

# Fuentes alternativas gratuitas para petroleo (fallback)
# EIA (Energy Information Administration) — Nivel A
EIA_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/?api_key=DEMO&data[0]=value&frequency=daily&sort[0][column]=period&sort[0][direction]=desc&length=1"


def sep(char="─", ancho=66):
    print(char * ancho)

def titulo(texto, char="═"):
    sep(char)
    print(f"  {texto}")
    sep(char)

def s(val):
    return "+" if val >= 0 else ""


# ── SNDK ─────────────────────────────────────────────────────────────────────

def analizar_sndk():
    titulo(f"SNDK — SanDisk Corporation")
    try:
        t    = yf.Ticker(SNDK_TICKER)
        info = t.info
        precio      = info.get("currentPrice") or info.get("regularMarketPrice")
        open_precio = info.get("open") or info.get("regularMarketOpen")
        high        = info.get("dayHigh") or info.get("regularMarketDayHigh")
        low         = info.get("dayLow") or info.get("regularMarketDayLow")
        prev_close  = info.get("previousClose") or info.get("regularMarketPreviousClose")
        vol         = info.get("volume") or info.get("regularMarketVolume")
        market_cap  = info.get("marketCap")
        pe_ratio    = info.get("trailingPE") or info.get("forwardPE")
        nombre      = info.get("longName") or info.get("shortName", SNDK_TICKER)

        if not precio:
            print("  No se pudo obtener precio de SNDK.")
            return

        cambio_dia    = precio - prev_close if prev_close else 0
        cambio_dia_pct = (cambio_dia / prev_close) * 100 if prev_close else 0
        distancia_min  = ((precio - SNDK_ZONA_MIN) / SNDK_ZONA_MIN) * 100
        distancia_max  = ((precio - SNDK_ZONA_MAX) / SNDK_ZONA_MAX) * 100
        vs_consenso    = ((precio - SNDK_CONSENSO) / SNDK_CONSENSO) * 100

        print(f"  Empresa   : {nombre}")
        print(f"  Precio    : ${precio:.2f}  ({s(cambio_dia)}{cambio_dia:.2f} / {s(cambio_dia_pct)}{cambio_dia_pct:.1f}% hoy)")
        if open_precio:
            print(f"  Apertura  : ${open_precio:.2f}  |  Max: ${high:.2f}  |  Min: ${low:.2f}")
        if vol:
            print(f"  Volumen   : {vol:,}")
        if market_cap:
            print(f"  Market Cap: ${market_cap/1e9:.1f}B")
        if pe_ratio:
            print(f"  P/E ratio : {pe_ratio:.1f}")

        sep()
        print(f"  Zona entrada  : ${SNDK_ZONA_MIN} — ${SNDK_ZONA_MAX}")
        print(f"  Consenso anal.: ${SNDK_CONSENSO}  (precio actual {s(vs_consenso)}{vs_consenso:.1f}% sobre consenso)")
        print(f"  Beta          : {SNDK_BETA}  (alta volatilidad — amplifica el mercado)")
        print(f"  Earnings      : {SNDK_EARNINGS}")
        sep()

        # Senal de accion
        if precio <= SNDK_ZONA_MAX and precio >= SNDK_ZONA_MIN:
            print(f"  ACCION : ** ZONA DE ENTRADA ACTIVA **")
            print(f"  Precio en zona $580-$620 — evaluar entrada segun liquidez")
            print(f"  Kelly sugerido: 10-15% del capital disponible")
            print(f"  NOTA: Sin cash disponible actualmente — resolver liquidez primero")
        elif precio < SNDK_ZONA_MIN:
            print(f"  ACCION : PRECIO BAJO ZONA — revisar fundamentales antes de entrar")
            print(f"  Precio ${precio:.2f} esta ${SNDK_ZONA_MIN - precio:.2f} bajo la zona minima")
        else:
            print(f"  ACCION : ESPERAR — precio demasiado alto")
            print(f"  Precio ${precio:.2f} esta {distancia_min:.1f}% sobre zona entrada min (${SNDK_ZONA_MIN})")
            print(f"  Distancia hasta zona: -${precio - SNDK_ZONA_MAX:.2f} para tocar ${SNDK_ZONA_MAX}")
            if precio > SNDK_CONSENSO * 1.25:
                print(f"  [!] Precio >25% sobre consenso analistas — riesgo de corrección")

    except Exception as e:
        print(f"  Error al obtener datos de SNDK: {e}")


# ── Petroleo ──────────────────────────────────────────────────────────────────

def obtener_petroleo_yfinance():
    datos = {}
    for nombre, ticker in [("WTI", WTI_TICKER), ("Brent", BRENT_TICKER)]:
        try:
            t    = yf.Ticker(ticker)
            info = t.info
            precio      = info.get("regularMarketPrice") or info.get("currentPrice")
            prev_close  = info.get("regularMarketPreviousClose") or info.get("previousClose")
            if precio:
                cambio = precio - prev_close if prev_close else 0
                cambio_pct = (cambio / prev_close) * 100 if prev_close else 0
                datos[nombre] = {
                    "precio": precio,
                    "cambio": cambio,
                    "cambio_pct": cambio_pct,
                    "fuente": "yfinance [Nivel B]"
                }
        except Exception:
            pass
    return datos

def obtener_petroleo_eia():
    """Fallback: EIA API gratuita (Nivel A — fuente primaria oficial)."""
    try:
        r = requests.get(EIA_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            items = data.get("response", {}).get("data", [])
            if items:
                return float(items[0].get("value", 0)), "EIA [Nivel A — fuente primaria]"
    except Exception:
        pass
    return None, None

def analizar_petroleo():
    titulo("PETROLEO — WTI & BRENT  [Impacto directo en posiciones Iran]")

    datos = obtener_petroleo_yfinance()

    if not datos:
        print("  yfinance no disponible. Intentando fuente alternativa...")
        precio_eia, fuente_eia = obtener_petroleo_eia()
        if precio_eia:
            print(f"  WTI (EIA): ${precio_eia:.2f}  [{fuente_eia}]")
        else:
            # Mostrar datos del portfolio.json como referencia
            try:
                with open(PORTFOLIO_FILE, encoding="utf-8") as f:
                    p = json.load(f)
                macro = p.get("contexto_macro", {})
                print(f"  WTI   : ${macro.get('wti_usd', 'N/A')}  (ultimo dato en portfolio.json)")
                print(f"  Brent : ${macro.get('brent_usd', 'N/A')}  (ultimo dato en portfolio.json)")
                print(f"  [!] Datos offline — actualizar portfolio.json con precios reales")
            except Exception:
                print("  No se pudo obtener precio del petroleo.")
        return

    for nombre, d in datos.items():
        print(f"  {nombre:6s}: ${d['precio']:>8.2f}  ({s(d['cambio'])}{d['cambio']:.2f} / {s(d['cambio_pct'])}{d['cambio_pct']:.1f}%)  [{d['fuente']}]")

    sep()

    # Analisis de impacto en posiciones Iran
    brent = datos.get("Brent", {}).get("precio")
    wti   = datos.get("WTI",   {}).get("precio")

    ref_precio = brent or wti
    if ref_precio:
        print(f"  ANALISIS DE IMPACTO EN POSICIONES IRAN:")
        if ref_precio > 100:
            print(f"  [!] Brent/WTI sobre $100 — presion economica alta sobre Iran")
            print(f"      -> Favorece posicion NO: Iran bajo presion, conflicto dificil de resolver pronto")
            print(f"      -> Hormuz sigue restringido -> presion se mantiene")
        if ref_precio > 120:
            print(f"  [!!] Brent >$120 — nivel critico historico")
            print(f"       -> Presion internacional para negociar aumenta")
            print(f"       -> Riesgo de que EEUU fuerce ceasefire rapido para bajar precios")
            print(f"       -> REVISAR posicion NO ceasefire April 15 — riesgo aumentado")
        if ref_precio < 90:
            print(f"  [-] Petroleo bajando — menor presion para resolver conflicto rapidamente")
            print(f"      -> Favorece largo plazo de las posiciones NO")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    sep("═")
    print(f"  MONITOR DE PRECIOS — {ahora}")
    sep("═")
    print()

    analizar_sndk()
    print()
    analizar_petroleo()

    sep("═")
    print()


if __name__ == "__main__":
    main()
