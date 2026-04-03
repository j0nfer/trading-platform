# -*- coding: utf-8 -*-
"""
comparador_mercados.py — Cross-checker de mercados relacionados con el portfolio

Detecta incoherencias matemáticas entre mercados correlacionados,
posibles arbitrajes y oportunidades no incorporadas.

USO:
  python comparador_mercados.py              # Análisis completo
  python comparador_mercados.py --iran       # Solo grupo Iran
  python comparador_mercados.py --oil        # Solo grupo Petróleo
  python comparador_mercados.py --macro      # Solo grupo Macro
  python comparador_mercados.py --arb        # Solo arbitrajes detectados
"""

import sys
import io
import os
import json
import time
import requests
from datetime import datetime
from typing import Optional

# Forzar UTF-8 en Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

GAMMA_API = "https://gamma-api.polymarket.com"

# ─── Definición de grupos de mercados ────────────────────────────────────────

GRUPOS = {
    "IRAN": {
        "descripcion": "Mercados de conflicto Iran/Ceasefire",
        "relacion": "temporal_inclusion",  # Apr15 ⊂ Jun30 ⊂ Dec31 ⊂ 2027
        "mercados": [
            {
                "nombre": "Ceasefire Apr 15 ★",
                "slug": "us-x-iran-ceasefire-by-april-15-182-528-637",
                "deadline": "2026-04-15",
                "tipo": "ceasefire",
                "nuestra_pos": "NO",
                "nuestra_entrada": 0.657,
                "nuestros_shares": 304.3,
            },
            {
                "nombre": "Ceasefire Apr 30",
                "slug": "us-x-iran-ceasefire-by-april-30-194-679-389",
                "deadline": "2026-04-30",
                "tipo": "ceasefire",
                "nuestra_pos": None,
                "nuestra_entrada": None,
            },
            {
                "nombre": "Conflict ends Jun 30 ★",
                "slug": "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725",
                "deadline": "2026-06-30",
                "tipo": "conflict_end",
                "nuestra_pos": "NO",
                "nuestra_entrada": 0.24,
                "nuestros_shares": 558.8,
            },
            {
                "nombre": "Regime falls Jun 30",
                "slug": "will-the-iranian-regime-fall-by-june-30",
                "deadline": "2026-06-30",
                "tipo": "regime_change",
                "nuestra_pos": None,
                "nuestra_entrada": None,
            },
            {
                "nombre": "Regime falls end 2026",
                "slug": "will-the-iranian-regime-fall-by-the-end-of-2026",
                "deadline": "2026-12-31",
                "tipo": "regime_change",
                "nuestra_pos": None,
                "nuestra_entrada": None,
            },
            {
                "nombre": "US forces enter Apr30",
                "slug": "us-forces-enter-iran-by-april-30-899",
                "deadline": "2026-04-30",
                "tipo": "escalada",
                "nuestra_pos": None,
                "nuestra_entrada": None,
            },
        ],
        "reglas_consistencia": [
            {
                "tipo": "inclusion_temporal",
                "descripcion": "P(A) <= P(B) si deadline A < deadline B para mismo evento",
                "pares": [
                    ("Ceasefire Apr 15", "Conflict ends Jun 30"),
                    ("Ceasefire Apr 15", "Ceasefire Dec 31"),
                    ("Conflict ends Jun 30", "Iran war ends 2027"),
                ],
            }
        ]
    },
    "PETROLEO": {
        "descripcion": "Mercados de petróleo relacionados con Iran",
        "relacion": "inversa",
        "mercados": [
            {
                "nombre": "WTI > $100 (Mar)",
                "slug": "will-crude-oil-cl-hit-high-100-by-end-of-march-658-396-769-971",
                "tipo": "commodity",
                "nuestra_pos": None,
                "brent_actual": None,  # se llena dinámicamente
            },
            {
                "nombre": "Ukraine ceasefire 2026",
                "slug": "russia-x-ukraine-ceasefire-before-2027",
                "tipo": "geopolitico",
                "nuestra_pos": None,
            },
            {
                "nombre": "Iran regime falls Jun30",
                "slug": "will-the-iranian-regime-fall-by-june-30",
                "tipo": "geopolitico",
                "nuestra_pos": None,
            },
        ],
        "relaciones_esperadas": [
            "Si P(ceasefire) sube → P(Brent>120) baja",
            "Si P(Brent>120) sube → P(ceasefire) baja",
            "Si hay incoherencia → hay edge en alguno de los dos",
        ]
    },
    "MACRO": {
        "descripcion": "Mercados macroeconómicos USA",
        "relacion": "mixta",
        "mercados": [
            {
                "nombre": "US Recesión 2026",
                "slug": "will-the-us-enter-a-recession-in-2026",
                "tipo": "macro",
                "nuestra_pos": None,
                "impacto_iran": "positivo",  # guerra → recesión
            },
            {
                "nombre": "Fed sin cambio Mayo",
                "slug": "fed-hold-may-2026",
                "tipo": "fed",
                "nuestra_pos": None,
                "impacto_iran": "positivo",
            },
            {
                "nombre": "Warsh Fed Chair",
                "slug": "will-kevin-warsh-be-confirmed-as-fed-chair",
                "tipo": "fed",
                "nuestra_pos": None,
                "impacto_iran": "neutro",
            },
        ]
    },
    "IMOS": {
        "descripcion": "IPOs tech 2026 (correlacion con sentiment)",
        "relacion": "inversa_guerra",
        "mercados": [
            {
                "nombre": "SpaceX IPO before 2027",
                "slug": "spacex-ipo-before-2027",
                "tipo": "ipo",
                "nuestra_pos": "NO",
                "nuestra_entrada": 0.09,
            },
            {
                "nombre": "OpenAI IPO before 2027",
                "slug": "openai-ipo-2026",
                "tipo": "ipo",
                "nuestra_pos": None,
            },
            {
                "nombre": "Anthropic IPO 2026",
                "slug": "anthropic-ipo-2026",
                "tipo": "ipo",
                "nuestra_pos": None,
            },
        ]
    }
}

# ─── API Helpers ─────────────────────────────────────────────────────────────

def _precio_valido(prices, idx: int = 0) -> Optional[float]:
    if not prices:
        return None
    try:
        if isinstance(prices, str):
            prices = json.loads(prices)
        p = float(str(prices[idx]).strip('"\''))
        return p if 0.02 <= p <= 0.98 else None
    except Exception:
        return None


def obtener_precio_mercado(slug: str) -> dict:
    """Retorna {yes, no, volumen, cerrado} para un mercado."""
    try:
        r = requests.get(f"{GAMMA_API}/markets",
                         params={"slug": slug}, timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json()
        if not data:
            return {}
        m = data[0] if isinstance(data, list) else data

        if m.get("closed"):
            return {"cerrado": True}

        prices   = m.get("outcomePrices", [])
        outcomes = m.get("outcomes", [])
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)

        # Identificar índice YES y NO
        idx_yes, idx_no = 0, 1
        for i, o in enumerate(outcomes):
            if isinstance(o, str):
                if o.strip().upper() == "YES":
                    idx_yes = i
                elif o.strip().upper() == "NO":
                    idx_no = i

        p_yes = _precio_valido(prices, idx_yes)
        p_no  = _precio_valido(prices, idx_no)

        if p_yes is None and p_no is not None:
            p_yes = round(1 - p_no, 4)
        elif p_no is None and p_yes is not None:
            p_no = round(1 - p_yes, 4)

        try:
            vol = float(m.get("volumeNum") or m.get("volume") or 0)
        except Exception:
            vol = 0

        return {
            "yes": p_yes,
            "no": p_no,
            "volumen": vol,
            "pregunta": m.get("question", "")[:80],
            "cerrado": False,
        }
    except Exception as e:
        return {"error": str(e)}


def obtener_brent_actual() -> Optional[float]:
    """Obtiene precio Brent desde Yahoo Finance."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BZ%3DF"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception:
        pass
    return None


# ─── Análisis de consistencia ─────────────────────────────────────────────────

def verificar_inclusion_temporal(mercados_con_precios: list) -> list:
    """
    Para mercados con relación de inclusión temporal:
    P(evento por T1) <= P(evento por T2) si T1 < T2
    Retorna lista de incoherencias.
    """
    incoherencias = []
    for i in range(len(mercados_con_precios) - 1):
        a = mercados_con_precios[i]
        b = mercados_con_precios[i + 1]
        pa = a.get("precio", {}).get("yes")
        pb = b.get("precio", {}).get("yes")
        if pa is None or pb is None:
            continue
        # P(A antes) debe ser <= P(B antes) porque B da más tiempo
        if pa > pb + 0.02:  # tolerancia 2%
            incoherencias.append({
                "tipo": "inclusion_temporal_violada",
                "mercado_a": a["nombre"],
                "mercado_b": b["nombre"],
                "p_a": pa,
                "p_b": pb,
                "diferencia": round(pa - pb, 3),
                "descripcion": (
                    f"P({a['nombre']} YES) = {pa:.0%} > "
                    f"P({b['nombre']} YES) = {pb:.0%}. "
                    f"INCOHERENTE: el plazo mayor debería tener P más alta."
                ),
                "arbitraje": (
                    f"Comprar YES en {b['nombre']} @ {pb:.0%} y "
                    f"vender/NO en {a['nombre']} @ {1-pa:.0%}. "
                    f"Edge teórico: {(pa - pb)*100:.1f}pp"
                )
            })
    return incoherencias


def verificar_correlacion_oil(precios_iran: dict, precios_oil: dict,
                              brent_actual: Optional[float]) -> list:
    """
    Verifica relación inversa entre ceasefire y petróleo.
    """
    hallazgos = []

    p_ceasefire_yes = precios_iran.get("yes")
    p_brent_120_yes = precios_oil.get("yes")

    if p_ceasefire_yes is None or p_brent_120_yes is None:
        return hallazgos

    # Relación esperada: ceasefire YES ↑ → Brent>120 YES ↓
    # Si Brent actual > $112 y P(Brent>120) < 40% → posible incoherencia
    if brent_actual and brent_actual > 110:
        umbral_brent = (brent_actual - 120) / brent_actual
        # Si Brent está a <10% de $120 y P(Brent>120) < 55%
        if abs(umbral_brent) < 0.10 and p_brent_120_yes < 0.55:
            hallazgos.append({
                "tipo": "brent_subestimado",
                "descripcion": (
                    f"Brent actual ${brent_actual:.1f} está a "
                    f"{abs(umbral_brent)*100:.1f}% de $120, "
                    f"pero P(Brent>$120) = {p_brent_120_yes:.0%}. "
                    f"Mercado puede estar subestimando la probabilidad."
                ),
                "accion": f"Considerar YES Brent>$120 @ {p_brent_120_yes:.0%}"
            })

    # Consistencia ceasefire vs Brent
    # Si P(ceasefire YES) es bajo (guerra continúa) → P(Brent>120) debería ser alta
    consistencia_esperada = 1 - p_ceasefire_yes  # aprox P(guerra continúa)
    discrepancia = abs(consistencia_esperada - p_brent_120_yes)

    if discrepancia > 0.25:
        hallazgos.append({
            "tipo": "discrepancia_ceasefire_oil",
            "descripcion": (
                f"P(ceasefire YES) = {p_ceasefire_yes:.0%} implica "
                f"P(guerra continúa) ≈ {consistencia_esperada:.0%}, "
                f"pero P(Brent>$120) = {p_brent_120_yes:.0%}. "
                f"Discrepancia de {discrepancia*100:.1f}pp."
            ),
            "edge_potencial": discrepancia,
            "accion": (
                f"Si confías en la posición Iran, el mercado de Brent puede "
                f"estar {'subestimado' if p_brent_120_yes < consistencia_esperada else 'sobreestimado'}. "
                f"Revisar con fuentes A."
            )
        })

    return hallazgos


def verificar_consistencia_macro(precios_iran: dict, precios_macro: dict) -> list:
    """
    Un conflicto Iran con Brent >$110 debería elevar P(recesión).
    """
    hallazgos = []
    p_war = precios_iran.get("no")  # P(NO ceasefire) = P(guerra continúa)
    p_rec = precios_macro.get("recesion_yes")

    if p_war is None or p_rec is None:
        return hallazgos

    # Si P(guerra) > 80% y P(recesión) < 50% → posible subestimación recesión
    if p_war > 0.80 and p_rec < 0.50:
        hallazgos.append({
            "tipo": "recesion_subestimada",
            "descripcion": (
                f"P(conflicto Iran continúa) = {p_war:.0%} pero "
                f"P(recesión USA 2026) = {p_rec:.0%}. "
                f"Con Brent >$110 y guerra en curso, la recesión podría "
                f"estar subestimada en el mercado."
            ),
            "edge_potencial": round(p_war * 0.6 - p_rec, 3),
            "accion": f"Analizar YES recesión 2026 @ {p_rec:.0%}. Requiere 2 fuentes A/B."
        })

    return hallazgos


# ─── Output ────────────────────────────────────────────────────────────────────

def imprimir_grupo(nombre_grupo: str, mercados_con_precios: list):
    """Imprime precios de un grupo de mercados."""
    print(f"\n  GRUPO: {nombre_grupo}")
    print(f"  {'-'*60}")
    print(f"  {'Mercado':<28}  {'YES':>6}  {'NO':>6}  {'Vol $M':>8}  Pos")
    print(f"  {'-'*60}")
    for m in mercados_con_precios:
        p = m.get("precio", {})
        if p.get("cerrado"):
            print(f"  {m['nombre']:<28}  [CERRADO]")
            continue
        if p.get("error") or not p:
            print(f"  {m['nombre']:<28}  [SIN DATOS]")
            continue
        yes_str = f"{p.get('yes', 0):.0%}" if p.get("yes") else "N/D"
        no_str  = f"{p.get('no', 0):.0%}"  if p.get("no")  else "N/D"
        vol_m   = f"${p.get('volumen', 0)/1e6:.2f}M" if p.get("volumen") else "N/D"
        pos_str = f"→ {m.get('nuestra_pos', '')} @ {m.get('nuestra_entrada', 0):.0%}" \
                  if m.get("nuestra_pos") else ""
        print(f"  {m['nombre']:<28}  {yes_str:>6}  {no_str:>6}  {vol_m:>8}  {pos_str}")
    print(f"  {'-'*60}")


def imprimir_incoherencia(inc: dict, num: int):
    print(f"\n  {num}. {inc['tipo'].upper()}")
    print(f"     {inc['descripcion']}")
    if inc.get("arbitraje"):
        print(f"     ARBITRAJE: {inc['arbitraje']}")
    if inc.get("accion"):
        print(f"     ACCION: {inc['accion']}")
    if inc.get("edge_potencial"):
        print(f"     Edge potencial: {inc['edge_potencial']*100:.1f}pp")


# ─── Main ──────────────────────────────────────────────────────────────────────

def analizar_grupo_iran():
    """Analiza el grupo de mercados Iran y detecta incoherencias."""
    grupo = GRUPOS["IRAN"]
    mercados = grupo["mercados"]

    print(f"\n  Obteniendo precios Iran...")
    mercados_con_precios = []
    for m in mercados:
        p = obtener_precio_mercado(m["slug"])
        time.sleep(0.3)
        m_copia = dict(m)
        m_copia["precio"] = p
        mercados_con_precios.append(m_copia)
        estado = f"{p.get('yes', 'N/D'):.0%} YES" if p.get("yes") else "sin datos"
        print(f"     {m['nombre']:<28} {estado}")

    imprimir_grupo("IRAN", mercados_con_precios)

    # Verificar consistencia temporal (solo mercados del mismo tipo)
    ceasefires = [m for m in mercados_con_precios
                  if m["tipo"] == "ceasefire" and m["precio"].get("yes") is not None]
    regimes    = [m for m in mercados_con_precios
                  if m["tipo"] == "regime_change" and m["precio"].get("yes") is not None]
    escaladas  = [m for m in mercados_con_precios
                  if m["tipo"] == "escalada" and m["precio"].get("yes") is not None]
    incoherencias  = verificar_inclusion_temporal(ceasefires)
    incoherencias += verificar_inclusion_temporal(regimes)

    return mercados_con_precios, incoherencias


def analizar_grupo_petroleo(p_ceasefire_yes: Optional[float]):
    """Analiza mercados de petróleo y su relación con Iran."""
    grupo = GRUPOS["PETROLEO"]
    mercados = grupo["mercados"]

    print(f"\n  Obteniendo precios Petróleo...")
    brent = obtener_brent_actual()
    if brent:
        print(f"     Brent actual: ${brent:.2f}")

    mercados_con_precios = []
    precio_brent_120 = {}
    for m in mercados:
        p = obtener_precio_mercado(m["slug"])
        time.sleep(0.3)
        m_copia = dict(m)
        m_copia["precio"] = p
        mercados_con_precios.append(m_copia)
        estado = f"{p.get('yes', 0):.0%} YES" if p.get("yes") else "sin datos"
        print(f"     {m['nombre']:<28} {estado}")
        if "brent" in m["nombre"].lower() or "120" in m["nombre"]:
            precio_brent_120 = p

    imprimir_grupo("PETROLEO", mercados_con_precios)

    hallazgos = []
    if p_ceasefire_yes is not None:
        hallazgos = verificar_correlacion_oil(
            {"yes": p_ceasefire_yes},
            {"yes": precio_brent_120.get("yes")},
            brent
        )

    return mercados_con_precios, hallazgos, brent


def analizar_grupo_macro(p_ceasefire_no: Optional[float]):
    """Analiza consistencia de mercados macro con el conflicto."""
    grupo = GRUPOS["MACRO"]
    mercados = grupo["mercados"]

    print(f"\n  Obteniendo precios Macro...")
    mercados_con_precios = []
    precios = {}
    for m in mercados:
        p = obtener_precio_mercado(m["slug"])
        time.sleep(0.3)
        m_copia = dict(m)
        m_copia["precio"] = p
        mercados_con_precios.append(m_copia)
        estado = f"{p.get('yes', 0):.0%} YES" if p.get("yes") else "sin datos"
        print(f"     {m['nombre']:<28} {estado}")
        if "recesion" in m["nombre"].lower() or "recession" in m["slug"].lower():
            precios["recesion_yes"] = p.get("yes")

    imprimir_grupo("MACRO", mercados_con_precios)

    hallazgos = []
    if p_ceasefire_no is not None and precios.get("recesion_yes"):
        hallazgos = verificar_consistencia_macro(
            {"no": p_ceasefire_no},
            precios
        )

    return mercados_con_precios, hallazgos


def analizar_grupo_ipos():
    """Analiza IPOs tech y su relación con el entorno de mercado."""
    grupo = GRUPOS["IMOS"]
    mercados = grupo["mercados"]

    print(f"\n  Obteniendo precios IPOs...")
    mercados_con_precios = []
    for m in mercados:
        p = obtener_precio_mercado(m["slug"])
        time.sleep(0.3)
        m_copia = dict(m)
        m_copia["precio"] = p
        mercados_con_precios.append(m_copia)
        estado = f"{p.get('yes', 0):.0%} YES" if p.get("yes") else "sin datos"
        print(f"     {m['nombre']:<28} {estado}")

    imprimir_grupo("IPOs TECH 2026", mercados_con_precios)

    # Detectar incoherencias: todos los IPOs deberían tener precio bajo
    # si los mercados están en tendencia bajista por la guerra
    hallazgos = []
    ipo_altos = [m for m in mercados_con_precios
                 if m["precio"].get("yes", 0) > 0.30]
    if ipo_altos:
        for m in ipo_altos:
            hallazgos.append({
                "tipo": "ipo_posiblemente_sobreestimado",
                "descripcion": (
                    f"{m['nombre']}: P(IPO YES) = {m['precio'].get('yes', 0):.0%}. "
                    f"Con mercados bajistas globales y conflicto Iran activo, "
                    f"una probabilidad >30% puede estar sobreestimada."
                ),
                "accion": f"Revisar con fuentes A (SEC EDGAR) si hay S-1 confidencial."
            })

    return mercados_con_precios, hallazgos


def resumen_final(todas_incoherencias: list, brent: Optional[float],
                  mercados_iran: list):
    """Imprime el resumen ejecutivo final."""
    print(f"\n{'='*60}")
    print(f"  RESUMEN EJECUTIVO — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*60}")

    # Estado general
    p_apr15_no = None
    p_jun30_no = None
    for m in mercados_iran:
        nombre = m.get("nombre", "")
        if "Apr 15" in nombre and m.get("nuestra_pos"):
            p_apr15_no = m["precio"].get("no")
        elif "Jun 30" in nombre and "★" in nombre and m.get("nuestra_pos"):
            p_jun30_no = m["precio"].get("no")  # posición directa NO

    print(f"\n  POSICIONES ACTUALES:")
    if p_apr15_no:
        entrada = 0.657
        pnl = (p_apr15_no - entrada) * 304.3
        print(f"  • Ceasefire Apr15 NO: {p_apr15_no:.0%} "
              f"(entrada 65.7¢) P/L: {pnl:+.2f}$")
    if p_jun30_no is not None:
        entrada = 0.24
        pnl = (p_jun30_no - entrada) * 558.8
        print(f"  • Conflict Jun30 NO: {p_jun30_no:.0%} "
              f"(entrada 24¢) P/L: {pnl:+.2f}$")
    if brent:
        print(f"  • Brent actual: ${brent:.2f}")

    # Incoherencias
    total = len(todas_incoherencias)
    print(f"\n  INCOHERENCIAS DETECTADAS: {total}")
    if total == 0:
        print(f"  Todos los mercados son matemáticamente consistentes hoy.")
    else:
        for i, inc in enumerate(todas_incoherencias, 1):
            imprimir_incoherencia(inc, i)

    # Mejor oportunidad
    edges = [(inc, inc.get("edge_potencial", 0))
             for inc in todas_incoherencias if inc.get("edge_potencial")]
    if edges:
        mejor = max(edges, key=lambda x: x[1])
        print(f"\n  MEJOR OPORTUNIDAD DETECTADA:")
        print(f"  {mejor[0]['descripcion'][:120]}")
        print(f"  Edge potencial: {mejor[1]*100:.1f}pp")
        print(f"  ACCION: {mejor[0].get('accion', 'Investigar con fuentes A/B')}")

    print(f"\n{'='*60}\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    todas_incoherencias = []
    brent = None
    mercados_iran = []

    print(f"\n{'='*60}")
    print(f"  COMPARADOR DE MERCADOS — CROSS-CHECK POLYMARKET")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*60}")

    if arg in ("", "--iran", "--arb"):
        mercados_iran, incs_iran = analizar_grupo_iran()
        todas_incoherencias.extend(incs_iran)

    p_apr15_yes = None
    p_apr15_no  = None
    for m in mercados_iran:
        if "Apr" in m.get("nombre", ""):
            p_apr15_yes = m["precio"].get("yes")
            p_apr15_no  = m["precio"].get("no")

    if arg in ("", "--oil", "--arb"):
        mercados_oil, incs_oil, brent = analizar_grupo_petroleo(p_apr15_yes)
        todas_incoherencias.extend(incs_oil)

    if arg in ("", "--macro", "--arb"):
        mercados_macro, incs_macro = analizar_grupo_macro(p_apr15_no)
        todas_incoherencias.extend(incs_macro)

    if arg in ("", "--arb"):
        mercados_ipos, incs_ipos = analizar_grupo_ipos()
        todas_incoherencias.extend(incs_ipos)

    resumen_final(todas_incoherencias, brent, mercados_iran)


if __name__ == "__main__":
    main()
