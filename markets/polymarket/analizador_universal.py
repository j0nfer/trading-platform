"""
analizador_universal.py — Analizador profesional de mercados Polymarket
Soporta: deportes, geopolitica, economia, politica
Uso: python analizador_universal.py --slug SLUG --prob 15
     python analizador_universal.py --manual
     python analizador_universal.py --test
"""

import sys, os
sys.path.insert(0, "C:\\inversiones")

import argparse
import json
import requests
import datetime

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API  = "https://data-api.polymarket.com"
CAPITAL_TOTAL = 434.24
HOY = datetime.date(2026, 3, 30)

KEYWORDS_DEPORTES  = ["nhl","nba","nfl","mlb","stanley cup","super bowl","world series","champions league",
                       "world cup","wimbledon","championship","playoffs","finals","tournament","champion",
                       "hurricanes","avalanche","lakers","chiefs","yankees","football","basketball","hockey","soccer"]
KEYWORDS_GEO       = ["war","ceasefire","conflict","attack","iran","israel","russia","ukraine","nato",
                       "nuclear","sanctions","missile","troops","invasion","peace","deal","regime","coup","hostage"]
KEYWORDS_ECONOMIA  = ["fed","rate","inflation","recession","gdp","unemployment","cpi","interest","hike",
                       "cut","boj","ecb","treasury","bond","yield","market","stock","crypto","bitcoin"]
KEYWORDS_POLITICA  = ["election","president","senate","congress","poll","vote","party","trump","biden",
                       "republican","democrat","impeach","resign","mayor","governor","legislation","bill"]

EFICIENCIA = {
    "deportes":   {"edge_min":12, "edge_bueno":20, "nota":"Compites vs modelos estadisticos profesionales. Edge real requiere >12pp"},
    "geopolitico":{"edge_min": 8, "edge_bueno":12, "nota":"Tu ventaja: fuentes multi-idioma y analisis macro. Mercado frecuentemente ineficiente"},
    "economia":   {"edge_min":10, "edge_bueno":18, "nota":"Muy eficiente. Solo edge con datos macro propios o antes de publicacion oficial"},
    "politico":   {"edge_min": 8, "edge_bueno":12, "nota":"Sesgo narrativo frecuente. Usar protocolo A/B de bloques opuestos"},
    "otro":       {"edge_min":10, "edge_bueno":15, "nota":"Tipo desconocido. Analisis manual requerido antes de entrar"},
}

def detectar_tipo(titulo: str, desc: str = "") -> str:
    texto = (titulo + " " + desc).lower()
    conteos = {
        "deportes":   sum(1 for k in KEYWORDS_DEPORTES  if k in texto),
        "geopolitico":sum(1 for k in KEYWORDS_GEO       if k in texto),
        "economia":   sum(1 for k in KEYWORDS_ECONOMIA  if k in texto),
        "politico":   sum(1 for k in KEYWORDS_POLITICA  if k in texto),
    }
    mejor = max(conteos, key=conteos.get)
    return mejor if conteos[mejor] > 0 else "otro"

def obtener_mercado(slug: str) -> dict:
    try:
        r = requests.get(f"{GAMMA_API}/markets?slug={slug}", timeout=10)
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        elif isinstance(data, dict):
            return data
    except Exception as e:
        print(f"[ERROR] No se pudo obtener mercado: {e}")
    return {}

def obtener_precios(mercado: dict) -> tuple:
    """Retorna (precio_yes, precio_no) como float 0-1"""
    try:
        raw = mercado.get("outcomePrices", "[]")
        if isinstance(raw, str):
            precios = json.loads(raw)
        else:
            precios = raw
        yes = float(precios[0]) if precios else 0.5
        no  = float(precios[1]) if len(precios) > 1 else (1 - yes)
        return yes, no
    except:
        return 0.5, 0.5

def obtener_volumen(mercado: dict) -> float:
    try:
        return float(mercado.get("volume", 0) or 0)
    except:
        return 0.0

def calcular_dias(end_date_str: str) -> int:
    if not end_date_str:
        return 999
    try:
        # Parse ISO 8601
        end_date_str = end_date_str[:10]
        end = datetime.date.fromisoformat(end_date_str)
        return max(0, (end - HOY).days)
    except:
        return 999

def calcular_kelly(prob_propia: float, precio_yes: float, fraccion: float = 0.25) -> float:
    if precio_yes <= 0 or precio_yes >= 1:
        return 0.0
    b = (1 - precio_yes) / precio_yes  # odds decimales menos 1
    p = prob_propia
    q = 1 - p
    kelly_full = (b * p - q) / b
    return max(0.0, kelly_full * fraccion)

def detectar_whales(slug: str, min_usd: float = 3000) -> list:
    whales = []
    try:
        url = f"{DATA_API}/trades?market={slug}&limit=200"
        r = requests.get(url, timeout=10)
        trades = r.json()
        if not isinstance(trades, list):
            return []
        ahora = datetime.datetime.now(datetime.timezone.utc)
        for t in trades:
            size = float(t.get("size", 0) or 0)
            if size >= min_usd:
                lado = t.get("side", "?").upper()
                ts_raw = t.get("timestamp", "") or t.get("createdAt", "")
                hace = "?"
                if ts_raw:
                    try:
                        ts = datetime.datetime.fromisoformat(ts_raw.replace("Z","+00:00"))
                        diff_h = (ahora - ts).total_seconds() / 3600
                        hace = f"{diff_h:.0f}h"
                    except:
                        pass
                whales.append({"monto": size, "lado": lado, "hace": hace})
    except Exception as e:
        pass
    return whales

def format_volumen(vol: float) -> str:
    if vol >= 1_000_000:
        return f"${vol/1_000_000:.1f}M"
    elif vol >= 1_000:
        return f"${vol/1_000:.0f}K"
    else:
        return f"${vol:.0f}"

def grade_liquidez(vol: float) -> str:
    if vol >= 5_000_000: return "Grado A (excelente)"
    if vol >= 500_000:   return "Grado B (buena)"
    if vol >= 50_000:    return "Grado C (aceptable)"
    return "Grado D (baja — posible edge pero riesgo manipulacion)"

def checklist(tipo: str, prob_propia: float, precio_yes: float, vol: float, dias: int,
              whales: list) -> dict:
    efic = EFICIENCIA.get(tipo, EFICIENCIA["otro"])
    edge_pp = abs(prob_propia - precio_yes) * 100
    scores = {}

    # 1. Base rate / calibracion del mercado
    if edge_pp >= 15:
        scores["base_rate"] = (3, f"Gran divergencia: tu estimacion {prob_propia:.0%} vs mercado {precio_yes:.0%} ({edge_pp:.1f}pp)")
    elif edge_pp >= 8:
        scores["base_rate"] = (2, f"Divergencia moderada: {edge_pp:.1f}pp entre tu estimacion y el mercado")
    elif edge_pp >= 3:
        scores["base_rate"] = (1, f"Divergencia leve: {edge_pp:.1f}pp — mercado probablemente bien calibrado")
    else:
        scores["base_rate"] = (0, f"Sin divergencia ({edge_pp:.1f}pp) — el mercado ya incorporo tu informacion")

    # 2. Incentivos / contexto del tipo
    if tipo == "deportes" and vol >= 1_000_000:
        scores["incentivos"] = (1, "Mercado deportivo muy liquido — modelos profesionales dominan, edge estructural dificil")
    elif tipo == "deportes":
        scores["incentivos"] = (2, "Mercado deportivo con liquidez moderada — posible ineficiencia si tienes info de lesiones/lineup")
    elif tipo == "geopolitico":
        scores["incentivos"] = (2, "Mercado geopolitico — tu analisis de fuentes A/B tiene ventaja comparativa real")
    else:
        scores["incentivos"] = (2, "Verificar manualmente si los incentivos de actores clave apoyan la tesis")

    # 3. Confirmacion fuentes A/B
    scores["fuentes"] = (2, "MANUAL: Verificar con 2+ fuentes nivel A/B de bloques opuestos antes de entrar")

    # 4. Macro coherente
    if tipo == "geopolitico":
        scores["macro"] = (2, "MANUAL: Verificar coherencia Brent/VIX/Gold con la tesis geopolitica")
    elif tipo == "economia":
        scores["macro"] = (2, "MANUAL: Verificar datos Fed, CPI, empleo antes de entrar")
    else:
        scores["macro"] = (2, "No aplica directamente — considerar contexto economico general del mercado")

    # 5. Whales
    whales_contra = [w for w in whales if (prob_propia > precio_yes and w["lado"] == "NO")
                     or (prob_propia < precio_yes and w["lado"] == "YES")]
    if whales_contra:
        total_whale = sum(w["monto"] for w in whales_contra)
        scores["whales"] = (0, f"ALERTA: ${total_whale:.0f} en whales apostando EN CONTRA — reducir posicion 50%")
    elif whales:
        total_whale = sum(w["monto"] for w in whales)
        scores["whales"] = (2, f"Whales a favor: ${total_whale:.0f} total — confirma direccion")
    else:
        scores["whales"] = (3, "Sin whales significativos detectados en contra")

    # 6. Edge suficiente
    if edge_pp >= efic["edge_bueno"]:
        scores["edge"] = (3, f"Edge {edge_pp:.1f}pp — supera umbral optimo ({efic['edge_bueno']}pp para {tipo})")
    elif edge_pp >= efic["edge_min"]:
        scores["edge"] = (2, f"Edge {edge_pp:.1f}pp — supera minimo ({efic['edge_min']}pp para {tipo})")
    elif edge_pp >= efic["edge_min"] / 2:
        scores["edge"] = (1, f"Edge marginal {edge_pp:.1f}pp — por debajo del minimo ({efic['edge_min']}pp para {tipo})")
    else:
        scores["edge"] = (0, f"Sin edge suficiente: {edge_pp:.1f}pp < {efic['edge_min']}pp minimo para {tipo}")

    # 7. Liquidez
    if vol >= 5_000_000:
        scores["liquidez"] = (3, f"Excelente: {format_volumen(vol)} — {grade_liquidez(vol)}")
    elif vol >= 500_000:
        scores["liquidez"] = (3, f"Buena: {format_volumen(vol)} — {grade_liquidez(vol)}")
    elif vol >= 50_000:
        scores["liquidez"] = (2, f"Aceptable: {format_volumen(vol)} — {grade_liquidez(vol)}")
    else:
        scores["liquidez"] = (0, f"Insuficiente: {format_volumen(vol)} — {grade_liquidez(vol)}")

    # 8. Plazo
    if 7 <= dias <= 30:
        scores["plazo"] = (3, f"{dias} dias — sweet spot corto plazo (mayor rentabilidad anualizada)")
    elif 30 < dias <= 60:
        scores["plazo"] = (3, f"{dias} dias — sweet spot medio-corto plazo")
    elif 60 < dias <= 120:
        scores["plazo"] = (2, f"{dias} dias — medio plazo, capital bloqueado tiempo considerable")
    elif dias <= 7:
        scores["plazo"] = (2, f"{dias} dias — muy corto, poco tiempo para mover precio")
    else:
        scores["plazo"] = (1, f"{dias} dias — largo plazo, alto costo de oportunidad del capital")

    # 9. Claridad resolucion
    scores["resolucion"] = (2, "MANUAL: Leer criterios exactos de resolucion en descripcion del contrato")

    # 10. Sin hype reciente
    scores["hype"] = (2, "MANUAL: Verificar si precio se movio >10pp en ultimas 24h (sesgo disponibilidad)")

    total = sum(v[0] for v in scores.values())
    return {"scores": scores, "total": total}

def verdict(total: int, edge_pp: float, tipo: str, kelly_pct: float) -> str:
    efic = EFICIENCIA.get(tipo, EFICIENCIA["otro"])
    capital_recomendado = CAPITAL_TOTAL * kelly_pct
    if total < 15:
        return f"NO RECOMENDADO ({total}/30) — Score insuficiente\n   {efic['nota']}"
    elif total < 20:
        return (f"SOLO MENCION ({total}/30) — Edge o eficiencia no justifican entrada\n"
                f"   {efic['nota']}\n"
                f"   Capital max si entras: ${capital_recomendado:.2f} (Kelly 25%: {kelly_pct*100:.1f}%)")
    elif total < 25:
        return (f"RECOMENDACION DEBIL ({total}/30) — Entrar con capital reducido\n"
                f"   Capital recomendado: ${capital_recomendado:.2f} (maximo 5% = ${CAPITAL_TOTAL*0.05:.2f})\n"
                f"   Recuerda: Regla de Oro #5 — esperar 24h si >$30")
    else:
        return (f"RECOMENDACION FUERTE ({total}/30) — Edge y fundamentales alineados\n"
                f"   Capital recomendado: ${capital_recomendado:.2f} (Kelly 25%: {kelly_pct*100:.1f}%)\n"
                f"   Maximo: 10-15% portfolio = ${CAPITAL_TOTAL*0.10:.0f}-${CAPITAL_TOTAL*0.15:.0f}\n"
                f"   Recuerda: completar diario_trading.py --nuevo antes de ejecutar")

def imprimir_checklist(resultado: dict) -> None:
    nombres = {
        "base_rate":   " 1. Base rate / calibracion   ",
        "incentivos":  " 2. Incentivos alineados       ",
        "fuentes":     " 3. Fuentes A/B confirmadas    ",
        "macro":       " 4. Macro coherente            ",
        "whales":      " 5. Sin whales en contra       ",
        "edge":        " 6. Edge suficiente            ",
        "liquidez":    " 7. Liquidez suficiente        ",
        "plazo":       " 8. Plazo en sweet spot        ",
        "resolucion":  " 9. Resolucion sin ambiguedad  ",
        "hype":        "10. Sin efecto hype reciente   ",
    }
    scores = resultado["scores"]
    for key, label in nombres.items():
        if key in scores:
            pts, razon = scores[key]
            barra = "\u2588" * pts + "\u2591" * (3 - pts)
            print(f"   {label}: {pts}/3 [{barra}] {razon}")
    print(f"\n   {'\u2500'*49}")
    total = resultado["total"]
    barra_total = "\u2588" * (total // 3) + "\u2591" * (10 - total // 3)
    print(f"   TOTAL: {total}/30 [{barra_total}]")
    if total >= 25:   nivel = "RECOMENDACION FUERTE"
    elif total >= 20: nivel = "RECOMENDACION DEBIL"
    elif total >= 15: nivel = "SOLO MENCION"
    else:             nivel = "NO RECOMENDADO"
    print(f"   Nivel: {nivel}")

def analizar_mercado(slug: str, prob_propia: float, tipo_forzado: str = "auto") -> None:
    print("\n" + "="*65)
    print(" ANALIZADOR UNIVERSAL — Cargando datos...")
    print("="*65)

    mercado = obtener_mercado(slug)
    if not mercado:
        print(f"[ERROR] No se encontro el mercado con slug: {slug}")
        sys.exit(1)

    titulo = mercado.get("question", slug)
    desc   = mercado.get("description", "")
    end_date = mercado.get("endDate", "")
    active   = mercado.get("active", True)

    tipo = tipo_forzado if tipo_forzado != "auto" else detectar_tipo(titulo, desc)
    yes, no = obtener_precios(mercado)
    vol  = obtener_volumen(mercado)
    dias = calcular_dias(end_date)

    print(f"\n{'='*65}")
    print(f" ANALISIS UNIVERSAL — {titulo[:55]}")
    print(f"{'='*65}")
    print(f" Slug            : {slug}")
    print(f" Tipo detectado  : {tipo.upper()}")
    print(f" Estado          : {'ACTIVO' if active else 'INACTIVO'}")
    print(f" Precio YES      : {yes*100:.1f}%")
    print(f" Precio NO       : {no*100:.1f}%")
    print(f" Tu estimacion   : {prob_propia*100:.1f}%")
    print(f" Volumen total   : {format_volumen(vol)} — {grade_liquidez(vol)}")
    print(f" Dias resolucion : {dias} dias (hasta {end_date[:10] if end_date else 'N/A'})")
    efic_nota = EFICIENCIA.get(tipo, EFICIENCIA["otro"])["nota"]
    print(f" Eficiencia      : {efic_nota[:60]}")

    # Whales
    print(f"\n{'-'*65}")
    print(" RASTREO DE WHALES (trades >= $3000)")
    print(f"{'-'*65}")
    whales = detectar_whales(slug)
    if whales:
        for w in whales[:5]:
            print(f"   ${w['monto']:.0f} — {w['lado']} — hace {w['hace']}")
        if len(whales) > 5:
            print(f"   ... y {len(whales)-5} mas")
    else:
        print("   Sin whales significativos detectados (o API no devolvio datos)")

    # Checklist
    print(f"\n{'-'*65}")
    print(" CHECKLIST DE DECISION — 10 CRITERIOS (0-3 pts c/u)")
    print(f"{'-'*65}")
    resultado = checklist(tipo, prob_propia, yes, vol, dias, whales)
    imprimir_checklist(resultado)

    # Kelly
    kelly_pct = calcular_kelly(prob_propia, yes)
    edge_pp = abs(prob_propia - yes) * 100
    kelly_usd = CAPITAL_TOTAL * kelly_pct
    print(f"\n{'-'*65}")
    print(" KELLY CRITERION")
    print(f"{'-'*65}")
    print(f"   Edge            : {edge_pp:+.1f}pp ({prob_propia:.0%} propia vs {yes:.0%} mercado)")
    kelly_full = calcular_kelly(prob_propia, yes, fraccion=1.0)
    print(f"   Kelly completo  : {kelly_full*100:.1f}% del portfolio")
    print(f"   Kelly 25%       : {kelly_pct*100:.1f}% del portfolio")
    print(f"   Capital Kelly   : ${kelly_usd:.2f}")
    print(f"   Capital max 15% : ${CAPITAL_TOTAL*0.15:.2f} (limite por mercado)")
    capital_final = min(kelly_usd, CAPITAL_TOTAL * 0.15)
    print(f"   Capital final   : ${capital_final:.2f}")

    # Veredicto
    print(f"\n{'-'*65}")
    print(" VEREDICTO FINAL")
    print(f"{'-'*65}")
    print(f"   {verdict(resultado['total'], edge_pp, tipo, kelly_pct)}")
    print(f"\n{'='*65}\n")

def modo_manual() -> None:
    print("\n" + "="*55)
    print(" ANALIZADOR MANUAL — Introduce los datos del mercado")
    print("="*55)
    nombre = input(" Nombre del mercado: ").strip() or "Mercado desconocido"
    tipo_input = input(" Tipo [deportes/geo/economia/politico/otro] (Enter=auto): ").strip().lower()
    try:
        precio_yes_pct = float(input(" Precio YES en Polymarket (0-100): ").strip())
    except:
        precio_yes_pct = 50.0
    try:
        prob_pct = float(input(" Tu probabilidad propia estimada (0-100): ").strip())
    except:
        prob_pct = 50.0
    try:
        vol = float(input(" Volumen USD aprox (ej: 58800000): ").strip())
    except:
        vol = 0.0
    try:
        dias = int(input(" Dias hasta resolucion: ").strip())
    except:
        dias = 90

    tipo = tipo_input if tipo_input in EFICIENCIA else detectar_tipo(nombre)
    yes = precio_yes_pct / 100
    prob = prob_pct / 100

    print(f"\n Tipo detectado: {tipo.upper()}")
    resultado = checklist(tipo, prob, yes, vol, dias, [])
    print(f"\n{'-'*55}")
    print(" CHECKLIST:")
    print(f"{'-'*55}")
    imprimir_checklist(resultado)
    kelly_pct = calcular_kelly(prob, yes)
    edge_pp = abs(prob - yes) * 100
    print(f"\n{'-'*55}")
    print(f" VEREDICTO:")
    print(f"{'-'*55}")
    print(f"   {verdict(resultado['total'], edge_pp, tipo, kelly_pct)}")
    print()

def test_carolina() -> None:
    """Test con datos reales de Carolina Hurricanes"""
    print("\n" + "="*65)
    print(" TEST — Carolina Hurricanes Stanley Cup 2026")
    print(" (Datos al 30/03/2026)")
    print("="*65)
    print(" Polymarket YES  : 12.0%")
    print(" DraftKings      : ~18.2% (odds +450)")
    print(" FanDuel         : ~14.3% (odds +600)")
    print(" Promedio SB     : ~16.3%")
    print(" Volumen Poly    : $58.8M (Grado A)")
    print(" Dias resolucion : 92 (hasta 30 jun)")
    print()

    yes = 0.12
    prob_sb = 0.163  # sportsbook average
    edge_pp = (prob_sb - yes) * 100

    resultado = checklist("deportes", prob_sb, yes, 58_800_000, 92, [])
    print(f"{'-'*65}")
    print(" CHECKLIST (usando prob sportsbooks como estimacion propia):")
    print(f"{'-'*65}")
    imprimir_checklist(resultado)

    kelly_pct = calcular_kelly(prob_sb, yes)
    print(f"\n{'-'*65}")
    print(" ANALISIS DE EFICIENCIA:")
    print(f"{'-'*65}")
    print(f"   Gap Poly vs SB  : +{edge_pp:.1f}pp (Polymarket infravalora YES)")
    print(f"   Umbral deportes : 12pp minimo, 20pp optimo")
    print(f"   Conclusion      : Gap {edge_pp:.1f}pp < 12pp minimo -> SIN EDGE SUFICIENTE")
    print(f"   Razon del gap   : Fees Polymarket (~2%) + diferente liquidez + eficiencia del mercado")
    print()
    print(f"   Kelly 25%       : {kelly_pct*100:.1f}% = ${CAPITAL_TOTAL*kelly_pct:.2f}")
    print(f"\n{'-'*65}")
    print(" VEREDICTO:")
    print(f"{'-'*65}")
    print(f"   {verdict(resultado['total'], edge_pp, 'deportes', kelly_pct)}")
    print(f"\n{'='*65}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Analizador universal de mercados Polymarket — sports + geopolitica",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python analizador_universal.py --test
  python analizador_universal.py --manual
  python analizador_universal.py --slug us-x-iran-ceasefire-by-april-15 --prob 14
  python analizador_universal.py --slug will-the-2026-nhl-stanley-cup --prob 16 --tipo deportes
        """
    )
    parser.add_argument("--slug",   help="Slug del mercado en Polymarket")
    parser.add_argument("--prob",   type=float, default=None, help="Tu probabilidad propia estimada (0-100)")
    parser.add_argument("--tipo",   default="auto", choices=["auto","deportes","geo","economia","politico","otro"])
    parser.add_argument("--manual", action="store_true", help="Modo interactivo manual")
    parser.add_argument("--test",   action="store_true", help="Test con Carolina Hurricanes")
    args = parser.parse_args()

    if args.test:
        test_carolina()
    elif args.manual:
        modo_manual()
    elif args.slug:
        if args.prob is None:
            print("[INFO] No especificaste --prob. Usando 50% como estimacion propia.")
            print("[INFO] Usa --prob XX para una estimacion personalizada (ej: --prob 15)")
        prob = (args.prob or 50) / 100
        analizar_mercado(args.slug, prob, args.tipo)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
