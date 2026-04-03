"""
comparador_odds.py — Compara precios Polymarket vs sportsbooks para detectar edge real
Uso:
  python comparador_odds.py --test           (Carolina Hurricanes case)
  python comparador_odds.py --nhl            (tabla completa NHL 2026)
  python comparador_odds.py --manual         (modo interactivo)
  python comparador_odds.py --odds +450 +600 --poly 12 --nombre "Carolina Hurricanes"
"""

import sys, os
sys.path.insert(0, "C:\\inversiones")

import argparse
import json
import requests

CAPITAL_TOTAL = 434.24

# Datos NHL 2026 Stanley Cup (actualizar manualmente)
NHL_2026 = [
    {"equipo": "Colorado Avalanche",   "poly": 20.0, "sb1": 28.6, "sb2": 25.0,
     "sb1_odds": "+250", "sb2_odds": "+300",
     "notas": "42-10-9, +82 GD — favorito absoluto. Poly lo infravalora."},
    {"equipo": "Carolina Hurricanes",  "poly": 12.0, "sb1": 18.2, "sb2": 14.3,
     "sb1_odds": "+450", "sb2_odds": "+600",
     "notas": "Lideres Metropolitana 96pts. Andersen .871 SV% — riesgo playoffs."},
    {"equipo": "Tampa Bay Lightning",  "poly": 14.0, "sb1": 11.1, "sb2": 12.5,
     "sb1_odds": "+800", "sb2_odds": "+700",
     "notas": "SOBREVALUADO en Polymarket vs sportsbooks (+2.4pp)."},
    {"equipo": "Dallas Stars",         "poly":  8.5, "sb1":  8.3, "sb2":  9.1,
     "sb1_odds": "+1100","sb2_odds": "+1000",
     "notas": "Bien calibrado — sin edge significativo."},
    {"equipo": "Buffalo Sabres",       "poly":  6.0, "sb1":  3.2, "sb2":  4.0,
     "sb1_odds": "+3000","sb2_odds": "+2400",
     "notas": "SOBREVALUADO en Poly — mercado narrativo (fans optimistas)."},
    {"equipo": "Edmonton Oilers",      "poly":  6.0, "sb1":  5.6, "sb2":  6.3,
     "sb1_odds": "+1700","sb2_odds": "+1500",
     "notas": "Bien calibrado. McDavid factor siempre presente."},
    {"equipo": "Vegas Golden Knights", "poly":  5.0, "sb1":  7.7, "sb2":  6.7,
     "sb1_odds": "+1200","sb2_odds": "+1400",
     "notas": "INFRAVALORADO en Poly — experiencia playoffs ignorada."},
    {"equipo": "Minnesota Wild",       "poly":  5.0, "sb1":  4.5, "sb2":  5.3,
     "sb1_odds": "+2100","sb2_odds": "+1800",
     "notas": "Bien calibrado."},
    {"equipo": "Montreal Canadiens",   "poly":  3.0, "sb1":  3.2, "sb2":  2.9,
     "sb1_odds": "+3000","sb2_odds": "+3300",
     "notas": "Sorpresa de la temporada. Bien calibrado."},
]


def odds_americanos_a_prob(odds_str: str) -> float:
    """Convierte odds americanos (+450, -200) a probabilidad implicita"""
    try:
        odds = int(odds_str.replace("+","").replace(" ",""))
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    except:
        return 0.0


def eliminar_vig(probs: list) -> list:
    """Normaliza lista de probabilidades eliminando el vig del libro"""
    total = sum(probs)
    if total <= 0:
        return probs
    return [p / total for p in probs]


def calcular_gap(poly_pct: float, ref_pct: float) -> dict:
    gap = ref_pct - poly_pct
    abs_gap = abs(gap)
    direccion = "YES (Poly subestima)" if gap > 0 else "NO (Poly sobreestima)"

    if abs_gap < 3:
        semaforo = "⚪"
        accion = "Sin edge significativo — mercado bien arbitrado"
        nivel = "NEUTRO"
    elif abs_gap < 7:
        semaforo = "🟡"
        accion = "Edge marginal — solo entrar si checklist >20/30"
        nivel = "MARGINAL"
    elif abs_gap < 12:
        semaforo = "🟠"
        accion = "Edge real — analizar con checklist completo, puede valer la pena"
        nivel = "REAL"
    else:
        semaforo = "🔴"
        accion = "Gap grande — verificar si hay error o informacion asimetrica"
        nivel = "GRANDE"

    return {
        "gap": gap, "abs_gap": abs_gap, "direccion": direccion,
        "semaforo": semaforo, "accion": accion, "nivel": nivel
    }


def analizar_equipo(equipo_data: dict, verbose: bool = True) -> dict:
    e = equipo_data
    sb_avg = (e["sb1"] + e["sb2"]) / 2
    analisis = calcular_gap(e["poly"], sb_avg)

    if verbose:
        gap_str = f"{analisis['gap']:+.1f}pp"
        print(f"\n{'─'*60}")
        print(f" 🏒 {e['equipo']}")
        print(f"    Polymarket    : {e['poly']:.1f}%  |  SB1: {e['sb1']:.1f}% ({e.get('sb1_odds','?')})  |  SB2: {e['sb2']:.1f}% ({e.get('sb2_odds','?')})")
        print(f"    Promedio SB   : {sb_avg:.1f}%")
        print(f"    Gap           : {analisis['semaforo']} {gap_str} → {analisis['direccion']}")
        print(f"    Nivel edge    : {analisis['nivel']}")
        print(f"    Accion        : {analisis['accion']}")
        print(f"    Notas         : {e['notas']}")

    return {**equipo_data, "sb_avg": sb_avg, "analisis": analisis}


def analizar_nhl_completo() -> None:
    print("\n" + "═"*60)
    print(" COMPARADOR NHL 2026 STANLEY CUP — Polymarket vs Sportsbooks")
    print(" Fuentes: DraftKings + FanDuel (30/03/2026)")
    print("═"*60)

    resultados = []
    for equipo in NHL_2026:
        r = analizar_equipo(equipo, verbose=True)
        resultados.append(r)

    # Ordenar por abs_gap
    resultados.sort(key=lambda x: x["analisis"]["abs_gap"], reverse=True)

    # Top oportunidades
    mejor_yes = max(resultados, key=lambda x: x["analisis"]["gap"])
    mejor_no  = min(resultados, key=lambda x: x["analisis"]["gap"])

    print(f"\n{'═'*60}")
    print(" RESUMEN DE OPORTUNIDADES")
    print(f"{'═'*60}")
    print(f"\n Mayor gap YES (Poly subestima):")
    print(f"   → {mejor_yes['equipo']}: {mejor_yes['analisis']['gap']:+.1f}pp")
    print(f"   Poly {mejor_yes['poly']}% vs SB avg {mejor_yes['sb_avg']:.1f}%")

    print(f"\n Mayor gap NO (Poly sobreestima):")
    print(f"   → {mejor_no['equipo']}: {mejor_no['analisis']['gap']:+.1f}pp")
    print(f"   Poly {mejor_no['poly']}% vs SB avg {mejor_no['sb_avg']:.1f}%")

    print(f"\n{'─'*60}")
    print(" RECOMENDACION PARA JON")
    print(f"{'─'*60}")
    print(f" Capital disponible: $0.01 USDC — SIN LIQUIDEZ ACTUAL")
    print(f" Post-15 abril: ~$220 disponibles (si Ceasefire Apr15 resuelve NO)")
    print()

    # Find actionable opportunities (gap > 7)
    oportunidades = [r for r in resultados if r["analisis"]["abs_gap"] >= 7]
    if oportunidades:
        print(f" Oportunidades con gap >7pp:")
        for o in oportunidades:
            dir_txt = "YES" if o["analisis"]["gap"] > 0 else "NO"
            print(f"   {o['analisis']['semaforo']} {o['equipo']} {dir_txt} — gap {o['analisis']['gap']:+.1f}pp")
        print()
        print(f" TOP PICK si hubiera capital: {oportunidades[0]['equipo']}")
        print(f"   → {oportunidades[0]['analisis']['direccion']}")
        print(f"   → Pero: mercado $58.8M = MUY EFICIENTE para deportes")
        print(f"   → Edge minimo deportes = 12pp. Gap actual = {oportunidades[0]['analisis']['abs_gap']:.1f}pp")
        print(f"   → CONCLUSION: Gap no justifica entrada en mercado de alta eficiencia")
    else:
        print(f" Ningun equipo supera el umbral de 7pp de edge.")
        print(f" El mercado NHL en Polymarket esta bien arbitrado vs sportsbooks.")

    print(f"\n{'═'*60}\n")


def modo_interactivo() -> None:
    print("\n" + "═"*55)
    print(" COMPARADOR MANUAL — Introduce los precios")
    print("═"*55)
    nombre = input(" Nombre del mercado/equipo: ").strip() or "Mercado"

    try:
        poly = float(input(" Precio YES en Polymarket (0-100%): ").strip())
    except:
        poly = 50.0

    refs = []
    i = 1
    while True:
        entrada = input(f" Referencia externa {i} (% o odds americanos como +450, Enter=terminar): ").strip()
        if not entrada:
            break
        if entrada.startswith("+") or entrada.startswith("-"):
            prob = odds_americanos_a_prob(entrada) * 100
            print(f"   → Convertido: {entrada} = {prob:.1f}% probabilidad implicita")
            refs.append(prob)
        else:
            try:
                refs.append(float(entrada))
            except:
                print("   Formato invalido, ignorado.")
        i += 1

    if not refs:
        print("[ERROR] Necesitas al menos una referencia externa.")
        return

    avg_ref = sum(refs) / len(refs)
    analisis = calcular_gap(poly, avg_ref)

    print(f"\n{'─'*55}")
    print(f" ANALISIS: {nombre}")
    print(f"{'─'*55}")
    print(f"   Polymarket    : {poly:.1f}%")
    for idx, r in enumerate(refs, 1):
        print(f"   Referencia {idx}  : {r:.1f}%")
    print(f"   Promedio ref  : {avg_ref:.1f}%")
    print(f"   Gap           : {analisis['semaforo']} {analisis['gap']:+.1f}pp → {analisis['direccion']}")
    print(f"   Nivel edge    : {analisis['nivel']}")
    print(f"   Accion        : {analisis['accion']}")
    print()


def test_carolina() -> None:
    print("\n" + "═"*65)
    print(" TEST — Carolina Hurricanes vs. Polymarket")
    print(" Stanley Cup 2026 — Datos al 30/03/2026")
    print("═"*65)

    poly = 12.0
    dk = odds_americanos_a_prob("+450") * 100   # 18.2%
    fd = odds_americanos_a_prob("+600") * 100   # 14.3%
    avg = (dk + fd) / 2

    print(f"\n Polymarket YES  : {poly:.1f}%")
    print(f" DraftKings      : {dk:.1f}% (odds +450)")
    print(f" FanDuel         : {fd:.1f}% (odds +600)")
    print(f" Promedio SB     : {avg:.1f}%")

    analisis = calcular_gap(poly, avg)
    print(f"\n{'─'*65}")
    print(f" Gap             : {analisis['semaforo']} {analisis['gap']:+.1f}pp — {analisis['direccion']}")
    print(f" Nivel edge      : {analisis['nivel']}")
    print()

    print(f"{'─'*65}")
    print(" INTERPRETACION:")
    print(f"{'─'*65}")
    print(f"   Gap de {analisis['abs_gap']:.1f}pp esta POR DEBAJO del umbral de 12pp para deportes")
    print(f"   Mercado de $58.8M: ALTAMENTE EFICIENTE (Grado A)")
    print(f"   El gap {analisis['gap']:+.1f}pp puede explicarse por:")
    print(f"     - Fees de Polymarket (~2%)")
    print(f"     - Diferente liquidez y timing de actualizacion")
    print(f"     - El mercado ya incorporo la prima de division leader")
    print()
    print(f"{'─'*65}")
    print(" CONCLUSION:")
    print(f"{'─'*65}")
    print(f"   {analisis['semaforo']} Sin edge suficiente para recomendar posicion")
    print(f"   → Monitorizar: si gap sube a >12pp, reconsiderar")
    print(f"   → Mejor uso del capital: esperar oportunidades geopoliticas")
    print(f"     donde tienes ventaja comparativa real (fuentes A/B multi-idioma)")
    print(f"\n{'═'*65}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Compara precios Polymarket vs sportsbooks para detectar edge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python comparador_odds.py --test
  python comparador_odds.py --nhl
  python comparador_odds.py --manual
  python comparador_odds.py --odds +450 +600 --poly 12 --nombre "Carolina YES"
        """
    )
    parser.add_argument("--nhl",    action="store_true", help="Analisis completo NHL 2026")
    parser.add_argument("--test",   action="store_true", help="Test Carolina Hurricanes")
    parser.add_argument("--manual", action="store_true", help="Modo interactivo")
    parser.add_argument("--poly",   type=float, help="Precio YES en Polymarket (0-100)")
    parser.add_argument("--odds",   nargs="+",  help="Odds americanos externos (ej: +450 +600)")
    parser.add_argument("--refs",   nargs="+",  type=float, help="Referencias en porcentaje (ej: 18.2 14.3)")
    parser.add_argument("--nombre", default="Mercado", help="Nombre del mercado")
    args = parser.parse_args()

    if args.test:
        test_carolina()
    elif args.nhl:
        analizar_nhl_completo()
    elif args.manual:
        modo_interactivo()
    elif args.poly is not None:
        refs = []
        if args.odds:
            for o in args.odds:
                refs.append(odds_americanos_a_prob(o) * 100)
        if args.refs:
            refs.extend(args.refs)
        if not refs:
            print("[ERROR] Especifica --odds o --refs para comparar.")
            sys.exit(1)
        avg_ref = sum(refs) / len(refs)
        analisis = calcular_gap(args.poly, avg_ref)
        print(f"\n {args.nombre}")
        print(f" Polymarket: {args.poly:.1f}% | Promedio externo: {avg_ref:.1f}%")
        print(f" Gap: {analisis['semaforo']} {analisis['gap']:+.1f}pp → {analisis['accion']}\n")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
