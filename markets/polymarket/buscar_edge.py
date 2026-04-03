"""
buscar_edge.py
Busca mercados en Polymarket con volumen $1M-$30M que vencen en 90 dias,
y aplica el protocolo de 6 pasos de analisis de edge automaticamente.
"""
import sys
import requests
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

GAMMA_API    = "https://gamma-api.polymarket.com"
VOL_MIN      = 1_000_000
VOL_MAX      = 30_000_000
DIAS_MAX     = 90
EDGE_MINIMO  = 8      # pp minimo accionable
EDGE_ALTO    = 20     # pp alta conviccion
CAPITAL      = 434.24
MAX_POR_MERCADO_PCT   = 0.15
MAX_INSIDER_PCT       = 0.05
KELLY_FRACCION        = 0.25

# ── Protocolo 6 pasos ────────────────────────────────────────────────────────

def paso1_eficiencia(volumen):
    if volumen < 500_000:
        return "C", "Tipo C — baja liquidez, manipulable"
    elif volumen < 5_000_000:
        return "B", "Tipo B — eficiencia media"
    else:
        return "A", "Tipo A — alta eficiencia"

def paso4_kelly(prob_propia, precio_mercado):
    """
    Calcula Kelly ajustado al 25%.
    prob_propia y precio_mercado son decimales (0-1).
    """
    if precio_mercado <= 0 or precio_mercado >= 1:
        return 0
    odds = (1 - precio_mercado) / precio_mercado
    edge = prob_propia - precio_mercado
    kelly_completo = edge / odds if odds > 0 else 0
    return max(0, kelly_completo * KELLY_FRACCION)

def paso5_riesgos(mercado):
    alertas = []
    q = mercado.get("question", "").lower()
    desc = str(mercado.get("description", "")).lower()

    if any(w in q + desc for w in ["trump", "executive order", "president"]):
        alertas.append("Trump effect (+/-15% incertidumbre adicional)")
    if any(w in q + desc for w in ["ceasefire", "peace", "deal", "agreement"]):
        alertas.append("Resolucion diplomatica — definicion puede ser ambigua (-30% prob)")
    if mercado.get("competitive", False) is False:
        alertas.append("Mercado poco competitivo — precio puede no reflejar informacion real")
    return alertas

def calcular_prob_base(precio_no, riesgos):
    """
    Aproxima probabilidad propia basada en el precio NO del mercado
    ajustada por riesgos identificados.
    Esta es una estimacion conservadora — requiere analisis manual con fuentes A/B.
    """
    # El precio NO ya es la probabilidad del mercado de que ocurra el NO
    prob = precio_no
    # Ajustes por riesgos
    for r in riesgos:
        if "ambigua" in r or "ambiguedad" in r.lower():
            prob *= 0.70   # -30% por ambiguedad
    return prob

def protocolo_6_pasos(mercado, precio_no):
    resultados = {}

    # Paso 1
    vol = mercado.get("volumeNum", 0) or 0
    tipo_eficiencia, desc_eficiencia = paso1_eficiencia(vol)
    resultados["paso1"] = {"tipo": tipo_eficiencia, "desc": desc_eficiencia, "volumen": vol}

    # Paso 2
    precio_yes = 1 - precio_no
    edge_no  = None  # requiere prob propia — marcado como pendiente
    resultados["paso2"] = {
        "precio_no": precio_no,
        "precio_yes": precio_yes,
        "nota": "Edge calculado requiere probabilidad propia con fuentes A/B"
    }

    # Paso 3
    riesgos = paso5_riesgos(mercado)
    resultados["paso3"] = {"riesgos": riesgos}

    # Paso 4 — Kelly con prob conservadora
    prob_conservadora = calcular_prob_base(precio_no, riesgos)
    kelly = paso4_kelly(prob_conservadora, precio_no)
    max_capital = CAPITAL * MAX_POR_MERCADO_PCT
    capital_kelly = CAPITAL * kelly
    capital_recomendado = min(capital_kelly, max_capital)
    resultados["paso4"] = {
        "kelly_fraccion": round(kelly, 4),
        "capital_kelly_usd": round(capital_kelly, 2),
        "capital_recomendado_usd": round(capital_recomendado, 2),
        "nota": "Basado en prob conservadora — ajustar con analisis manual A/B"
    }

    # Paso 5
    resultados["paso5"] = {"alertas": riesgos}

    # Paso 6 — Accion preliminar
    if tipo_eficiencia == "C":
        accion = "EVITAR — liquidez insuficiente"
    elif kelly <= 0:
        accion = "EVITAR — sin edge detectable"
    elif kelly < 0.02:
        accion = "ESPERAR — edge marginal, analizar con fuentes A/B"
    elif riesgos:
        accion = "INVESTIGAR — riesgos identificados, aplicar protocolo A/B completo"
    else:
        accion = "CANDIDATO — profundizar analisis con fuentes A/B"
    resultados["paso6"] = {"accion": accion}

    return resultados


# ── Fetch mercados Polymarket ────────────────────────────────────────────────

def obtener_mercados_por_volumen():
    """
    Descarga mercados activos de Polymarket, filtra por volumen y vencimiento,
    y los ordena por volumen descendente.
    """
    hoy       = datetime.utcnow().date()
    limite    = hoy + timedelta(days=DIAS_MAX)
    mercados  = []

    print("  Descargando mercados de Polymarket Gamma API...", flush=True)
    offset = 0
    batch  = 100
    paginas_max = 20   # hasta 2000 mercados

    for _ in range(paginas_max):
        try:
            r = requests.get(
                f"{GAMMA_API}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": batch,
                    "offset": offset,
                    "order": "volumeNum",
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
                vol = m.get("volumeNum") or 0
                if vol < VOL_MIN:
                    # Los mercados vienen ordenados por volumen desc — si ya es < min, parar
                    return mercados
                if vol > VOL_MAX:
                    offset += batch
                    continue

                # Filtrar por fecha
                end_raw = m.get("endDateIso") or m.get("endDate", "")
                if not end_raw:
                    offset += batch
                    continue
                try:
                    end_date = datetime.fromisoformat(end_raw.replace("Z", "")).date()
                except Exception:
                    continue

                if hoy <= end_date <= limite:
                    mercados.append(m)

            offset += batch

        except Exception as e:
            print(f"  Error en pagina offset={offset}: {e}")
            break

    return mercados

def extraer_precio_no(mercado):
    """Extrae el precio del outcome NO del mercado."""
    import json as _json
    prices = mercado.get("outcomePrices", [])
    outcomes = mercado.get("outcomes", [])
    # La API puede devolver outcomePrices como JSON string en vez de lista
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

    # Buscar indice de NO
    idx_no = 1  # default
    if isinstance(outcomes, list):
        for i, o in enumerate(outcomes):
            if str(o).lower() in ("no", "false"):
                idx_no = i
                break

    if isinstance(prices, list) and len(prices) > idx_no:
        try:
            return float(str(prices[idx_no]).strip('"\''))
        except Exception:
            pass

    # Fallback: lastTradePrice
    ltp = mercado.get("lastTradePrice")
    if ltp:
        try:
            return float(ltp)
        except Exception:
            pass

    return None


# ── Output ───────────────────────────────────────────────────────────────────

def sep(char="─", ancho=66):
    print(char * ancho)

def main():
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    sep("═")
    print(f"  BUSCADOR DE EDGE — POLYMARKET  [{ahora}]")
    sep("═")
    print(f"  Filtros: Volumen ${VOL_MIN/1e6:.0f}M-${VOL_MAX/1e6:.0f}M | Vencimiento proximos {DIAS_MAX} dias")
    print(f"  Capital referencia: ${CAPITAL} | Edge minimo: {EDGE_MINIMO}pp")
    print()

    mercados = obtener_mercados_por_volumen()

    if not mercados:
        print("  No se encontraron mercados con los filtros actuales.")
        print("  Prueba ampliar VOL_MIN o DIAS_MAX en el script.")
        print()

        # Mostrar muestra de mercados activos con mayor volumen para referencia
        print("  Muestra de mercados mas activos actualmente:")
        sep()
        try:
            r = requests.get(
                f"{GAMMA_API}/markets",
                params={"active": "true", "limit": 10, "order": "volumeNum", "ascending": "false"},
                timeout=15,
            )
            for m in r.json()[:5]:
                vol = m.get("volumeNum", 0) or 0
                end = m.get("endDateIso", m.get("endDate", "N/A"))[:10]
                print(f"  Vol: ${vol:>12,.0f} | Vence: {end} | {m.get('question','')[:55]}")
        except Exception as e:
            print(f"  Error: {e}")
        sep("═")
        return

    print(f"  Encontrados: {len(mercados)} mercados en rango\n")

    candidatos = []
    for m in sorted(mercados, key=lambda x: x.get("volumeNum", 0), reverse=True):
        precio_no = extraer_precio_no(m)
        if precio_no is None:
            continue
        resultado = protocolo_6_pasos(m, precio_no)
        accion = resultado["paso6"]["accion"]
        if "EVITAR" not in accion:
            candidatos.append((m, precio_no, resultado))

    if not candidatos:
        print("  Sin candidatos tras aplicar protocolo 6 pasos.")
    else:
        print(f"  Candidatos tras filtro: {len(candidatos)}\n")

    for m, precio_no, r in candidatos[:10]:
        vol      = m.get("volumeNum", 0) or 0
        end      = (m.get("endDateIso") or m.get("endDate", ""))[:10]
        hoy      = datetime.utcnow().date()
        try:
            dias = (datetime.fromisoformat(end).date() - hoy).days
        except Exception:
            dias = "?"

        sep()
        print(f"  MERCADO  : {m.get('question','')[:65]}")
        print(f"  Volumen  : ${vol:,.0f}  |  Vence: {end}  ({dias} dias)")
        print(f"  Precio NO: {precio_no:.3f}  |  Precio YES: {1-precio_no:.3f}")
        print(f"  Eficiencia  [P1]: {r['paso1']['desc']}")
        if r["paso3"]["riesgos"]:
            print(f"  Riesgos  [P3/5]: " + " | ".join(r["paso3"]["riesgos"][:2]))
        print(f"  Kelly    [P4]: {r['paso4']['kelly_fraccion']:.1%}  => ${r['paso4']['capital_recomendado_usd']:.2f} max")
        print(f"  ACCION   [P6]: {r['paso6']['accion']}")
        print(f"  NOTA         : Calcular prob propia con fuentes A/B antes de entrar")

    sep("═")
    print()
    print("  IMPORTANTE: Este script identifica candidatos preliminares.")
    print("  Antes de entrar, aplicar manualmente el Protocolo Paso 2:")
    print("  - Calcular probabilidad propia con fuentes Nivel A/B")
    print("  - Edge minimo accionable: +8pp sobre precio de mercado")
    print("  - Edge alta conviccion:  +20pp")
    print()


if __name__ == "__main__":
    main()
