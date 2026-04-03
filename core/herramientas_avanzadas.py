"""
herramientas_avanzadas.py
6 herramientas analiticas para trading en Polymarket:
  1. Calculadora Kelly avanzada
  2. Detector de arbitraje entre mercados relacionados
  3. Simulador de escenarios con valor esperado
  4. Monitor de correlaciones entre posiciones
  5. Diario de trading (diario.json)
  6. Indice de estres del portfolio (0-100)
"""
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"
HISTORIAL_FILE = Path(__file__).parent / "historial_trades.json"
DIARIO_FILE    = Path(__file__).parent / "diario.json"
GAMMA_API      = "https://gamma-api.polymarket.com"

CAPITAL_TOTAL      = 434.24
RESERVA_MIN_PCT    = 0.20
MAX_POR_MERCADO_PCT = 0.15


# ═══════════════════════════════════════════════════════════════════════════
# UTILIDADES COMUNES
# ═══════════════════════════════════════════════════════════════════════════

def sep(char="─", ancho=66):
    print(char * ancho)

def titulo(texto, char="═"):
    print(char * 66)
    print(f"  {texto}")
    print(char * 66)

def cargar_json(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def guardar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def s(val):
    return "+" if val >= 0 else ""


# ═══════════════════════════════════════════════════════════════════════════
# HERRAMIENTA 1 — CALCULADORA KELLY AVANZADA
# ═══════════════════════════════════════════════════════════════════════════

TIPOS_MERCADO = {
    "insider":     {"kelly_pct": 0.10, "max_pct": 0.05,  "desc": "Con insider documentado"},
    "geopolitico": {"kelly_pct": 0.15, "max_pct": 0.10,  "desc": "Mercado geopolitico (iran, guerra)"},
    "banco_central":{"kelly_pct": 0.25, "max_pct": 0.15, "desc": "Banco central (Fed, BCE)"},
    "elecciones":  {"kelly_pct": 0.20, "max_pct": 0.12,  "desc": "Elecciones con polling solido"},
    "general":     {"kelly_pct": 0.25, "max_pct": 0.15,  "desc": "Mercado general sin clasificar"},
}

def kelly_avanzado(prob_propia: float, precio_mercado: float,
                   capital: float = None, tipo_mercado: str = "general",
                   verbose: bool = True) -> dict:
    """
    Calcula el Kelly optimo segun tipo de mercado.

    Args:
        prob_propia    : probabilidad que asignas al outcome (0-1)
        precio_mercado : precio del mercado para ese outcome (0-1)
        capital        : capital disponible en USD (default: CAPITAL_TOTAL)
        tipo_mercado   : "insider"|"geopolitico"|"banco_central"|"elecciones"|"general"
        verbose        : mostrar output formateado

    Returns dict con kelly_completo, kelly_25, kelly_tipo, capital_recomendado, edge_pp
    """
    capital = capital or CAPITAL_TOTAL
    tipo    = TIPOS_MERCADO.get(tipo_mercado, TIPOS_MERCADO["general"])

    edge_pp   = (prob_propia - precio_mercado) * 100
    odds      = (1 - precio_mercado) / precio_mercado if precio_mercado > 0 else 0
    q         = 1 - prob_propia

    # Kelly completo = (p*b - q) / b  donde b = odds
    kelly_completo = (prob_propia * odds - q) / odds if odds > 0 else 0
    kelly_completo = max(0, kelly_completo)

    kelly_25    = kelly_completo * 0.25
    kelly_10    = kelly_completo * 0.10
    kelly_tipo  = kelly_completo * tipo["kelly_pct"]

    cap_kelly_25   = min(capital * kelly_25,   capital * MAX_POR_MERCADO_PCT)
    cap_kelly_10   = min(capital * kelly_10,   capital * 0.05)
    cap_kelly_tipo = min(capital * kelly_tipo, capital * tipo["max_pct"])
    cap_reserva    = capital * RESERVA_MIN_PCT

    resultado = {
        "prob_propia":       prob_propia,
        "precio_mercado":    precio_mercado,
        "edge_pp":           round(edge_pp, 2),
        "odds":              round(odds, 3),
        "kelly_completo":    round(kelly_completo, 4),
        "kelly_25pct":       round(kelly_25, 4),
        "kelly_10pct":       round(kelly_10, 4),
        "kelly_tipo":        round(kelly_tipo, 4),
        "capital_kelly_25":  round(cap_kelly_25, 2),
        "capital_kelly_10":  round(cap_kelly_10, 2),
        "capital_recomendado": round(cap_kelly_tipo, 2),
        "tipo_mercado":      tipo_mercado,
        "reserva_minima":    round(cap_reserva, 2),
        "capital_disponible": round(max(0, capital - cap_reserva), 2),
    }

    if verbose:
        titulo(f"KELLY AVANZADO — {tipo['desc']}")
        print(f"  Prob propia    : {prob_propia:.0%}  |  Precio mercado : {precio_mercado:.0%}")
        print(f"  Edge           : {s(edge_pp)}{edge_pp:.1f}pp  |  Odds : {odds:.2f}x")
        sep()
        print(f"  Kelly completo (teorico)    : {kelly_completo:.1%}  => ${capital * kelly_completo:.2f}")
        print(f"  Kelly 25%  (recomendado)    : {kelly_25:.1%}  => ${cap_kelly_25:.2f}")
        print(f"  Kelly 10%  (conservador)    : {kelly_10:.1%}  => ${cap_kelly_10:.2f}")
        print(f"  Kelly tipo [{tipo_mercado}]: {kelly_tipo:.1%}  => ${cap_kelly_tipo:.2f}  <- USAR ESTE")
        sep()
        print(f"  Capital total  : ${capital:.2f}")
        print(f"  Reserva minima : ${cap_reserva:.2f}  (20% intocable)")
        print(f"  Capital operable: ${resultado['capital_disponible']:.2f}")
        print(f"\n  CAPITAL RECOMENDADO: ${cap_kelly_tipo:.2f}")
        if edge_pp < 8:
            print(f"  [!] Edge < 8pp — no justifica entrada")
        elif edge_pp > 30:
            print(f"  [!] Edge > 30pp — busca activamente que estas pasando por alto")
        print()

    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# HERRAMIENTA 2 — DETECTOR DE ARBITRAJE
# ═══════════════════════════════════════════════════════════════════════════

def detectar_arbitraje(mercado_a: dict, mercado_b: dict, verbose: bool = True) -> dict:
    """
    Detecta inconsistencias matematicas entre dos mercados relacionados.

    Args:
        mercado_a / mercado_b: dicts con {pregunta, precio_yes, volumen, vencimiento}
    """
    p_a  = mercado_a.get("precio_yes", 0.5)
    p_b  = mercado_b.get("precio_yes", 0.5)
    diff = abs(p_a - p_b) * 100
    q_a  = mercado_a.get("pregunta", "Mercado A")[:60]
    q_b  = mercado_b.get("pregunta", "Mercado B")[:60]

    # Detectar inconsistencias tipicas
    inconsistencias = []

    # 1. Si A implica B, P(A) no puede ser mayor que P(B)
    #    Ej: "Warsh confirmado mayo" <= "Warsh confirmado junio"
    vc_a = mercado_a.get("vencimiento", "")
    vc_b = mercado_b.get("vencimiento", "")
    if vc_a and vc_b and vc_a < vc_b and p_a > p_b + 0.03:
        inconsistencias.append({
            "tipo":    "IMPLICACION_TEMPORAL",
            "detalle": f"Mercado con plazo MENOR ({vc_a}) tiene precio MAYOR ({p_a:.0%}) que mercado con plazo MAYOR ({vc_b}) precio ({p_b:.0%})",
            "oportunidad": f"Comprar NO en {q_a} y YES en {q_b} — diferencia arbitrable de {diff:.1f}pp",
        })

    # 2. Mercados complementarios que no suman ~100%
    if abs(mercado_a.get("tema", "") == mercado_b.get("tema", "")) or diff < 5:
        suma = p_a + p_b
        if suma < 0.90 or suma > 1.10:
            inconsistencias.append({
                "tipo":    "COMPLEMENTARIOS_DESEQUILIBRADOS",
                "detalle": f"Suma de precios: {suma:.0%} (deberia ser ~100% si son mutuamente excluyentes)",
                "oportunidad": f"{'Oportunidad YES en el mas bajo' if suma < 0.97 else 'Oportunidad NO en ambos'}",
            })

    # 3. Diferencia de precio sospechosamente pequeña entre plazos distintos
    if vc_a and vc_b:
        try:
            dias_diff = abs((datetime.strptime(vc_b[:10], "%Y-%m-%d") -
                             datetime.strptime(vc_a[:10], "%Y-%m-%d")).days)
            if dias_diff > 30 and diff < 5:
                inconsistencias.append({
                    "tipo":    "DIFERENCIA_TEMPORAL_INSUFICIENTE",
                    "detalle": f"{dias_diff} dias de diferencia pero solo {diff:.1f}pp de diferencia de precio",
                    "oportunidad": "Precio de plazo mas corto probablemente sobrevalorado",
                })
        except Exception:
            pass

    resultado = {
        "mercado_a":       q_a,
        "precio_a":        p_a,
        "mercado_b":       q_b,
        "precio_b":        p_b,
        "diferencia_pp":   round(diff, 2),
        "inconsistencias": inconsistencias,
    }

    if verbose:
        titulo("DETECTOR DE ARBITRAJE")
        sep()
        print(f"  Mercado A: {q_a}")
        print(f"  Precio A : {p_a:.0%}  |  Vence: {mercado_a.get('vencimiento','?')}")
        sep()
        print(f"  Mercado B: {q_b}")
        print(f"  Precio B : {p_b:.0%}  |  Vence: {mercado_b.get('vencimiento','?')}")
        sep()
        print(f"  Diferencia de precio: {diff:.1f}pp\n")
        if inconsistencias:
            print(f"  INCONSISTENCIAS DETECTADAS ({len(inconsistencias)}):\n")
            for inc in inconsistencias:
                print(f"  [!] {inc['tipo']}")
                print(f"      {inc['detalle']}")
                print(f"      Oportunidad: {inc['oportunidad']}\n")
        else:
            print("  Sin inconsistencias matematicas detectadas.")
        print()

    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# HERRAMIENTA 3 — SIMULADOR DE ESCENARIOS
# ═══════════════════════════════════════════════════════════════════════════

def simular_escenarios(posicion: dict, escenarios: list = None, verbose: bool = True) -> dict:
    """
    Simula escenarios para una posicion y calcula el valor esperado (EV).

    Args:
        posicion  : dict con {mercado, direccion, precio_entrada, shares, capital}
        escenarios: lista de dicts [{nombre, prob, precio_salida, descripcion}]
                    Si None, genera escenarios automaticos.

    Returns dict con EV, escenarios calculados.
    """
    precio_e = posicion.get("precio_entrada_avg", 0.5)
    shares   = posicion.get("shares", 0)
    capital  = posicion.get("capital_invertido", shares * precio_e)
    direccion = posicion.get("direccion", "NO")

    # Escenarios automaticos si no se proporcionan
    if escenarios is None:
        if direccion == "NO":
            escenarios = [
                {
                    "nombre":      "BASE — NO resuelve (conflicto continua)",
                    "prob":        0.75,
                    "precio_salida": 0.95,
                    "descripcion": "El conflicto no termina en el plazo. Posicion resuelve como ganada.",
                    "tipo":        "base",
                },
                {
                    "nombre":      "POSITIVO — Escalada confirma NO",
                    "prob":        0.10,
                    "precio_salida": 0.99,
                    "descripcion": "Nuevo evento de escalada aumenta certeza del NO. Precio llega a 99c.",
                    "tipo":        "positivo",
                },
                {
                    "nombre":      "NEGATIVO — Ceasefire sorpresa",
                    "prob":        0.15,
                    "precio_salida": 0.05,
                    "descripcion": "Acuerdo de paz bilateral publico. Posicion pierde casi todo.",
                    "tipo":        "negativo",
                },
            ]
        else:
            escenarios = [
                {
                    "nombre":      "BASE — YES resuelve como esperado",
                    "prob":        0.60,
                    "precio_salida": 0.95,
                    "descripcion": "El evento ocurre segun el analisis.",
                    "tipo":        "base",
                },
                {
                    "nombre":      "POSITIVO — Confirmacion anticipada",
                    "prob":        0.15,
                    "precio_salida": 0.99,
                    "descripcion": "El evento se confirma antes de la fecha, precio al maximo.",
                    "tipo":        "positivo",
                },
                {
                    "nombre":      "NEGATIVO — El evento no ocurre",
                    "prob":        0.25,
                    "precio_salida": 0.05,
                    "descripcion": "El evento no ocurre. Posicion pierde.",
                    "tipo":        "negativo",
                },
            ]

    # Calcular PnL por escenario
    resultados_esc = []
    ev_total = 0.0
    for esc in escenarios:
        pnl_abs = (esc["precio_salida"] - precio_e) * shares
        pnl_pct = (pnl_abs / capital) * 100 if capital else 0
        ev_esc  = esc["prob"] * pnl_abs
        ev_total += ev_esc
        resultados_esc.append({
            **esc,
            "pnl_absoluto": round(pnl_abs, 2),
            "pnl_pct":      round(pnl_pct, 1),
            "ev_parcial":   round(ev_esc, 2),
        })

    # Normalizar probas si no suman 100%
    suma_prob = sum(e["prob"] for e in escenarios)
    if abs(suma_prob - 1.0) > 0.01:
        for r in resultados_esc:
            r["prob"] = r["prob"] / suma_prob

    resultado = {
        "posicion":       posicion.get("mercado", "?")[:50],
        "capital":        capital,
        "ev_total":       round(ev_total, 2),
        "ev_positivo":    ev_total > 0,
        "escenarios":     resultados_esc,
    }

    if verbose:
        titulo(f"SIMULADOR DE ESCENARIOS — {posicion.get('mercado','?')[:50]}")
        print(f"  Posicion  : {direccion} @ {precio_e:.3f}  |  Shares: {shares:.1f}  |  Capital: ${capital:.2f}\n")
        sep()
        for r in resultados_esc:
            tipo_ico = {"base": "[ = ]", "positivo": "[+]", "negativo": "[-]"}.get(r["tipo"], "[ ? ]")
            print(f"  {tipo_ico} {r['nombre']}")
            print(f"       Prob: {r['prob']:.0%}  |  Precio salida: {r['precio_salida']:.2f}")
            print(f"       PnL: {s(r['pnl_absoluto'])}{r['pnl_absoluto']:.2f} USD ({s(r['pnl_pct'])}{r['pnl_pct']:.1f}%)")
            print(f"       Descripcion: {r['descripcion']}")
            print(f"       EV parcial: {s(r['ev_parcial'])}{r['ev_parcial']:.2f} USD\n")
        sep()
        ev_icon = "[V]" if ev_total > 0 else "[X]"
        print(f"\n  {ev_icon} VALOR ESPERADO TOTAL: {s(ev_total)}{ev_total:.2f} USD")
        if ev_total < 0:
            print("  [!] EV negativo — considera NO abrir o CERRAR esta posicion")
        elif ev_total < capital * 0.05:
            print("  [~] EV bajo — verifica si el riesgo compensa el retorno esperado")
        print()

    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# HERRAMIENTA 4 — MONITOR DE CORRELACIONES
# ═══════════════════════════════════════════════════════════════════════════

# Correlaciones conocidas entre tipos de eventos (simplificado, sin datos historicos)
CORRELACIONES_CONOCIDAS = [
    {
        "tipo_a": "iran_ceasefire",
        "tipo_b": "iran_conflict_end",
        "correlacion": 0.85,
        "razon": "Ambos dependen del mismo evento subyacente: fin del conflicto Iran",
        "riesgo": "Si hay ceasefire, AMBAS posiciones pierden. No es diversificacion real.",
    },
    {
        "tipo_a": "fed_rate_change",
        "tipo_b": "recession_2026",
        "correlacion": 0.70,
        "razon": "Subida de tipos aumenta prob de recesion; correlacionados negativamente",
        "riesgo": "Movimiento de la Fed afecta ambos mercados en la misma direccion",
    },
    {
        "tipo_a": "oil_price",
        "tipo_b": "iran_conflict",
        "correlacion": 0.75,
        "razon": "Conflicto Iran aumenta precio del petroleo directamente",
        "riesgo": "Posiciones en oil correlacionadas con posiciones Iran",
    },
]

def _clasificar_posicion(posicion):
    """Clasifica el tipo de una posicion para detectar correlaciones."""
    m = posicion.get("mercado", "").lower()
    if "iran" in m and "ceasefire" in m:
        return "iran_ceasefire"
    if "iran" in m and ("conflict" in m or "end" in m):
        return "iran_conflict_end"
    if "fed" in m or "rate" in m or "fomc" in m:
        return "fed_rate_change"
    if "recession" in m:
        return "recession_2026"
    if "oil" in m or "brent" in m or "wti" in m:
        return "oil_price"
    return "otro"

def monitor_correlaciones(posiciones: list, verbose: bool = True) -> list:
    """
    Detecta correlaciones entre posiciones abiertas.

    Args:
        posiciones: lista de dicts con datos de posiciones

    Returns lista de pares correlacionados con nivel de riesgo.
    """
    alertas = []
    tipos   = [(p, _clasificar_posicion(p)) for p in posiciones]

    for i, (p_a, tipo_a) in enumerate(tipos):
        for j, (p_b, tipo_b) in enumerate(tipos):
            if j <= i:
                continue
            # Buscar correlacion conocida
            for cor in CORRELACIONES_CONOCIDAS:
                match = (
                    (cor["tipo_a"] == tipo_a and cor["tipo_b"] == tipo_b) or
                    (cor["tipo_a"] == tipo_b and cor["tipo_b"] == tipo_a)
                )
                if match and cor["correlacion"] >= 0.60:
                    cap_a = p_a.get("capital_invertido", 0)
                    cap_b = p_b.get("capital_invertido", 0)
                    alertas.append({
                        "mercado_a":   p_a.get("mercado", "")[:50],
                        "mercado_b":   p_b.get("mercado", "")[:50],
                        "correlacion": cor["correlacion"],
                        "razon":       cor["razon"],
                        "riesgo":      cor["riesgo"],
                        "capital_combinado": round(cap_a + cap_b, 2),
                        "pct_portfolio": round((cap_a + cap_b) / CAPITAL_TOTAL * 100, 1),
                    })

    if verbose:
        titulo("MONITOR DE CORRELACIONES")
        if not alertas:
            print("  Sin correlaciones significativas detectadas (umbral: >60%).")
        else:
            print(f"  {len(alertas)} par(es) de posiciones correlacionadas detectados:\n")
            for a in alertas:
                nivel_ico = "[X]" if a["correlacion"] >= 0.80 else "[ ! ]"
                print(f"  {nivel_ico} Correlacion: {a['correlacion']:.0%}")
                print(f"       A: {a['mercado_a']}")
                print(f"       B: {a['mercado_b']}")
                print(f"       Capital combinado: ${a['capital_combinado']:.2f} ({a['pct_portfolio']:.0f}% del portfolio)")
                print(f"       Razon: {a['razon']}")
                print(f"       Riesgo: {a['riesgo']}")
                sep()
            print()
            print("  ACCION: Posiciones correlacionadas equivalen a UNA posicion grande.")
            print("  Reduce exposicion combinada al maximo del 50% del capital total.")
            print(f"  Limite actual: ${CAPITAL_TOTAL * 0.50:.2f}")
        print()

    return alertas


# ═══════════════════════════════════════════════════════════════════════════
# HERRAMIENTA 5 — DIARIO DE TRADING
# ═══════════════════════════════════════════════════════════════════════════

def _init_diario():
    if not DIARIO_FILE.exists():
        plantilla = {
            "_instrucciones": "Completar ANTES de cada trade. El diario es obligatorio (Regla 6).",
            "entradas": [],
            "estadisticas": {
                "total_trades": 0,
                "win_rate_pct": None,
                "sesgo_frecuente": None,
                "mejor_trade": None,
                "peor_trade":  None,
                "win_rate_por_tipo": {},
            }
        }
        guardar_json(DIARIO_FILE, plantilla)
    return cargar_json(DIARIO_FILE)

def registrar_diario_pre(mercado, precio, edge_calculado, fuentes, sesgos_detectados,
                         checklist_resultado, emocion_1_5, notas_pre=""):
    """
    Registra la entrada ANTES de ejecutar el trade.

    Args:
        emocion_1_5 : 1=frio/analitico, 3=neutral, 5=eufórico/ansioso
    """
    diario = _init_diario()
    ahora  = datetime.now().strftime("%Y-%m-%d %H:%M")

    ids = [e["id"] for e in diario["entradas"]]
    nuevo_id = max(ids) + 1 if ids else 1

    entrada = {
        "id":                nuevo_id,
        "estado":            "pre_trade",
        "timestamp_pre":     ahora,
        "mercado":           mercado,
        "precio_entrada":    precio,
        "edge_calculado_pp": edge_calculado,
        "fuentes":           fuentes,
        "sesgos_detectados": sesgos_detectados,
        "checklist_resultado": checklist_resultado,
        "emocion_entrada":   emocion_1_5,
        "notas_pre":         notas_pre,
        "timestamp_post":    None,
        "resultado":         None,
        "analisis_correcto": None,
        "edge_real_pp":      None,
        "sesgo_cometido":    None,
        "leccion":           "",
        "notas_post":        "",
    }
    diario["entradas"].append(entrada)
    diario["estadisticas"]["total_trades"] = len(diario["entradas"])
    guardar_json(DIARIO_FILE, diario)
    print(f"  [+] Diario #{nuevo_id} registrado (pre-trade): {mercado[:50]}")
    print(f"      Emocion: {emocion_1_5}/5  |  Checklist: {checklist_resultado}  |  Edge: {edge_calculado:+.1f}pp")
    return nuevo_id

def registrar_diario_post(entrada_id, resultado, analisis_correcto,
                          edge_real_pp, sesgo_cometido, leccion, notas_post=""):
    """
    Completa la entrada del diario DESPUES de la resolucion.
    """
    diario = _init_diario()
    entrada = next((e for e in diario["entradas"] if e["id"] == entrada_id), None)
    if entrada is None:
        print(f"  [!] Entrada #{entrada_id} no encontrada.")
        return

    entrada.update({
        "estado":            "post_trade",
        "timestamp_post":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "resultado":         resultado,
        "analisis_correcto": analisis_correcto,
        "edge_real_pp":      edge_real_pp,
        "sesgo_cometido":    sesgo_cometido,
        "leccion":           leccion,
        "notas_post":        notas_post,
    })

    # Actualizar estadisticas
    stats = diario["estadisticas"]
    completados = [e for e in diario["entradas"] if e.get("resultado")]
    ganados     = [e for e in completados if e["resultado"] == "ganado"]
    stats["win_rate_pct"] = round(len(ganados) / len(completados) * 100, 1) if completados else None

    # Sesgo mas frecuente
    sesgos = [e["sesgo_cometido"] for e in completados if e.get("sesgo_cometido")]
    if sesgos:
        from collections import Counter
        stats["sesgo_frecuente"] = Counter(sesgos).most_common(1)[0][0]

    guardar_json(DIARIO_FILE, diario)
    print(f"  [+] Diario #{entrada_id} completado: {resultado.upper()}")
    print(f"      Leccion: {leccion[:70]}")

def mostrar_diario(n=10):
    """Muestra las ultimas N entradas del diario."""
    diario = _init_diario()
    entradas = diario.get("entradas", [])
    stats    = diario.get("estadisticas", {})

    titulo("DIARIO DE TRADING")
    print(f"  Total entradas: {len(entradas)}  |  Win rate: {stats.get('win_rate_pct','N/D')}%")
    if stats.get("sesgo_frecuente"):
        print(f"  Sesgo mas frecuente: {stats['sesgo_frecuente']}")
    print()

    for e in entradas[-n:]:
        estado_ico = "[PRE]" if e["estado"] == "pre_trade" else ("[G]" if e.get("resultado") == "ganado" else "[P]")
        print(f"  {estado_ico} #{e['id']:02d} | {e['mercado'][:48]}")
        print(f"       {e.get('timestamp_pre','?')}  |  Edge: {e.get('edge_calculado_pp',0):+.1f}pp  |  Emocion: {e.get('emocion_entrada','?')}/5")
        if e.get("resultado"):
            ac = "[SI]" if e.get("analisis_correcto") else "[NO]"
            print(f"       Resultado: {e['resultado']}  |  Analisis correcto: {ac}  |  Sesgo: {e.get('sesgo_cometido','ninguno')}")
            if e.get("leccion"):
                print(f"       Leccion: {e['leccion'][:70]}")
        print()


# ═══════════════════════════════════════════════════════════════════════════
# HERRAMIENTA 6 — INDICE DE ESTRES DEL PORTFOLIO
# ═══════════════════════════════════════════════════════════════════════════

def calcular_indice_estres(portfolio: dict = None, historial: dict = None,
                            dias_mal_sueno: int = 0, pnl_dia_pct: float = 0,
                            verbose: bool = True) -> dict:
    """
    Calcula el indice de estres del portfolio (0-100).

    Args:
        portfolio       : datos del portfolio (carga automaticamente si None)
        historial       : historial de trades (carga automaticamente si None)
        dias_mal_sueno  : dias recientes con mal sueno por las posiciones (0-2)
        pnl_dia_pct     : P/L del dia en % (negativo = perdida)
        verbose         : mostrar output formateado

    Returns dict con puntuacion, nivel, factores.
    """
    if portfolio is None:
        portfolio = cargar_json(PORTFOLIO_FILE)
    if historial is None:
        historial = cargar_json(HISTORIAL_FILE)

    perfil    = portfolio.get("perfil", {})
    posiciones = portfolio.get("posiciones_polymarket", [])
    stats     = historial.get("estadisticas", {})

    puntos    = 0
    factores  = []

    capital_total = perfil.get("capital_total_usdc", CAPITAL_TOTAL)
    cash          = perfil.get("cash_disponible", 0)
    cash_pct      = (cash / capital_total) * 100 if capital_total else 0

    # ── FACTORES QUE AUMENTAN EL ESTRES ────────────────────────────────────

    if cash_pct < 10:
        puntos += 20
        factores.append({"factor": f"Cash < 10% del portfolio ({cash_pct:.1f}%)", "puntos": +20, "tipo": "riesgo"})

    # Correlacion entre posiciones
    correlaciones = monitor_correlaciones(posiciones, verbose=False)
    if any(c["correlacion"] >= 0.60 for c in correlaciones):
        puntos += 15
        factores.append({"factor": "Correlacion entre posiciones > 60%", "puntos": +15, "tipo": "riesgo"})

    # Posicion venciendo pronto
    hoy = datetime.today().date()
    for p in posiciones:
        try:
            dias = (datetime.strptime(p["fecha_resolucion"], "%Y-%m-%d").date() - hoy).days
            if dias <= 7:
                puntos += 15
                factores.append({"factor": f"'{p['mercado'][:35]}...' vence en {dias} dias", "puntos": +15, "tipo": "urgencia"})
        except Exception:
            pass

    # Insider documentado
    for p in posiciones:
        for r in p.get("riesgos", []):
            if "insider" in r.lower():
                puntos += 10
                factores.append({"factor": f"Insider documentado en '{p['mercado'][:35]}...'", "puntos": +10, "tipo": "riesgo"})
                break

    # P/L del dia negativo
    if pnl_dia_pct < -5:
        puntos += 10
        factores.append({"factor": f"P/L del dia: {pnl_dia_pct:.1f}% (< -5%)", "puntos": +10, "tipo": "rendimiento"})

    # Mal sueno
    if dias_mal_sueno >= 2:
        puntos += 10
        factores.append({"factor": f"{dias_mal_sueno} dias recientes con mal sueno por posiciones", "puntos": +10, "tipo": "psicologico"})
    elif dias_mal_sueno == 1:
        puntos += 5
        factores.append({"factor": "1 dia reciente con mal sueno por posiciones", "puntos": +5, "tipo": "psicologico"})

    # ── FACTORES QUE REDUCEN EL ESTRES ─────────────────────────────────────

    if cash_pct > 30:
        puntos -= 10
        factores.append({"factor": f"Cash > 30% ({cash_pct:.1f}%) — buena reserva", "puntos": -10, "tipo": "positivo"})

    # Win rate reciente > 60%
    wr = stats.get("win_rate_pct")
    if wr and wr > 60 and stats.get("resueltos", 0) >= 5:
        puntos -= 10
        factores.append({"factor": f"Win rate > 60% en historial ({wr:.1f}%)", "puntos": -10, "tipo": "positivo"})

    # Todas las posiciones con edge > 15pp (usando estimacion)
    todos_con_edge = all(
        t.get("edge_estimado_pp") and t["edge_estimado_pp"] > 15
        for t in historial.get("trades", [])
        if t["estado"] == "abierto"
    )
    if todos_con_edge and historial.get("trades"):
        puntos -= 10
        factores.append({"factor": "Todas las posiciones abiertas con edge > 15pp", "puntos": -10, "tipo": "positivo"})

    puntos = max(0, min(100, puntos))

    # Nivel de estres
    if puntos <= 30:
        nivel = "VERDE"
        accion = "Operar con normalidad. Sistema bajo control."
    elif puntos <= 60:
        nivel = "AMARILLO"
        accion = "Reducir tamaño de nuevos trades. No abrir posiciones grandes."
    elif puntos <= 80:
        nivel = "NARANJA"
        accion = "No abrir nuevas posiciones. Revisar las existentes."
    else:
        nivel = "ROJO"
        accion = "Considerar cerrar posiciones y descansar del mercado."

    resultado = {
        "puntuacion": puntos,
        "nivel":      nivel,
        "accion":     accion,
        "factores":   factores,
    }

    if verbose:
        titulo(f"INDICE DE ESTRES DEL PORTFOLIO")
        iconos = {"VERDE": "[V]", "AMARILLO": "[~]", "NARANJA": "[!]", "ROJO": "[X]"}
        icono  = iconos.get(nivel, "[?]")
        barra  = ("█" * (puntos // 5)).ljust(20, "░")
        print(f"\n  {icono} PUNTUACION: {puntos}/100  [{barra}]  NIVEL: {nivel}")
        print(f"  ACCION: {accion}\n")
        sep()
        print("  Factores:\n")
        for f in sorted(factores, key=lambda x: -abs(x["puntos"])):
            signo_ico = "[+]" if f["puntos"] > 0 else "[-]"
            print(f"  {signo_ico} {f['puntos']:+3d} pts  {f['factor']}")
        print()

    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — DEMO DE TODAS LAS HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 66)
    print("  HERRAMIENTAS AVANZADAS — DEMO")
    print("=" * 66)
    print()

    # 1. Kelly
    kelly_avanzado(
        prob_propia=0.82,
        precio_mercado=0.343,  # prob NO = 1 - 0.657
        capital=CAPITAL_TOTAL,
        tipo_mercado="geopolitico"
    )

    # 2. Arbitraje (ejemplo con mercados Iran)
    detectar_arbitraje(
        mercado_a={
            "pregunta":    "US x Iran ceasefire by April 15?",
            "precio_yes":  0.343,
            "vencimiento": "2026-04-15",
        },
        mercado_b={
            "pregunta":    "Iran conflict ends by June 30?",
            "precio_yes":  0.240,
            "vencimiento": "2026-06-30",
        }
    )

    # 3. Escenarios posicion 1
    simular_escenarios({
        "mercado":          "US x Iran ceasefire by April 15?",
        "direccion":        "NO",
        "precio_entrada_avg": 0.657,
        "shares":           304.3,
        "capital_invertido": 199.93,
    })

    # 4. Correlaciones
    posiciones_demo = [
        {"mercado": "US x Iran ceasefire by April 15?",        "capital_invertido": 199.93},
        {"mercado": "Iran x Israel/US conflict ends by June 30?", "capital_invertido": 134.11},
    ]
    monitor_correlaciones(posiciones_demo)

    # 5. Diario (solo muestra, no crea entrada nueva en demo)
    mostrar_diario()

    # 6. Indice de estres
    calcular_indice_estres(dias_mal_sueno=0, pnl_dia_pct=0)


if __name__ == "__main__":
    main()
