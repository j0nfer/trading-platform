"""
retroalimentacion.py
Sistema de aprendizaje continuo: registro pre/post trade, análisis de patrones,
simulación Monte Carlo y detector de errores sistémicos.

Uso:
  python retroalimentacion.py --informe         # informe de mejora personal
  python retroalimentacion.py --simular         # simulación Monte Carlo interactiva
  python retroalimentacion.py --sistemico       # detector de errores sistémicos
  python retroalimentacion.py --registro        # registrar nuevo análisis pre-trade
"""
import sys
import json
import math
import random
import argparse
from datetime import datetime
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

APRENDIZAJE_FILE = Path(__file__).parent / "aprendizaje.json"

# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def sep(char="─", ancho=66):
    print(char * ancho)

def titulo(texto, char="═"):
    sep(char)
    print(f"  {texto}")
    sep(char)

def cargar_aprendizaje():
    if not APRENDIZAJE_FILE.exists():
        return []
    try:
        with open(APRENDIZAJE_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def guardar_aprendizaje(registros):
    with open(APRENDIZAJE_FILE, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN 1 — REGISTRO PRE-TRADE
# ═══════════════════════════════════════════════════════════════════════════

def registro_pre_trade(
    mercado: str,
    precio_entrada: float,
    mi_probabilidad_estimada: float,
    fuentes_usadas: list,
    nivel_confianza: str,           # "ALTO" | "MEDIO" | "BAJO"
    razonamiento_principal: str,
    mejor_argumento_contrario: str,
    capital_arriesgado: float,
    indice_estres_momento: int,
    sesgos_detectados: list = None,
    sesgos_controlados: bool = False,
    fecha: str = None,
    notas: str = "",
) -> int:
    """
    Registra el análisis completo ANTES de ejecutar un trade.

    Retorna el ID del registro (para enlazar con post-resolución).

    Ejemplo:
        registro_pre_trade(
            mercado="SpaceX IPO before 2027 — NO",
            precio_entrada=0.09,
            mi_probabilidad_estimada=0.25,
            fuentes_usadas=["WSJ [B]", "CNBC [B]", "Reuters [B]", "SEC EDGAR [A]"],
            nivel_confianza="MEDIO",
            razonamiento_principal="S-1 inminente pero riesgos SEC/xAI/Iran...",
            mejor_argumento_contrario="IPO filing esta semana, target June 2026...",
            capital_arriesgado=15.0,
            indice_estres_momento=45,
            sesgos_detectados=["FOMO_RATIO", "OVERCONF"],
            sesgos_controlados=True
        )
    """
    if nivel_confianza not in ("ALTO", "MEDIO", "BAJO"):
        raise ValueError("nivel_confianza debe ser ALTO, MEDIO o BAJO")
    if not 0 < precio_entrada < 1:
        raise ValueError("precio_entrada debe estar entre 0 y 1")
    if not 0 < mi_probabilidad_estimada < 1:
        raise ValueError("mi_probabilidad_estimada debe estar entre 0 y 1")

    precio_mercado = precio_entrada
    edge_calculado = round((mi_probabilidad_estimada - precio_mercado) * 100, 2)

    registros = cargar_aprendizaje()
    nuevo_id   = max((r.get("id", 0) for r in registros), default=0) + 1

    registro = {
        "id":                        nuevo_id,
        "fase":                      "PRE",
        "fecha":                     fecha or datetime.now().strftime("%Y-%m-%d"),
        "hora":                      datetime.now().strftime("%H:%M"),
        "mercado":                   mercado,
        "precio_entrada":            precio_entrada,
        "precio_mercado":            precio_mercado,
        "mi_probabilidad_estimada":  mi_probabilidad_estimada,
        "edge_calculado_pp":         edge_calculado,
        "fuentes_usadas":            fuentes_usadas,
        "nivel_confianza":           nivel_confianza,
        "sesgos_detectados":         sesgos_detectados or [],
        "sesgos_controlados":        sesgos_controlados,
        "razonamiento_principal":    razonamiento_principal,
        "mejor_argumento_contrario": mejor_argumento_contrario,
        "capital_arriesgado":        capital_arriesgado,
        "indice_estres_momento":     indice_estres_momento,
        "notas":                     notas,
        # Campos post-resolución (se rellenan después)
        "resultado":                 None,
        "precio_salida":             None,
        "ganancia_real":             None,
        "mi_estimacion_fue":         None,
        "error_cometido":            None,
        "sesgo_que_no_detecte":      None,
        "leccion_aprendida":         None,
        "cambio_protocolo":          None,
        "fecha_resolucion":          None,
    }

    registros.append(registro)
    guardar_aprendizaje(registros)

    print(f"\n  [+] Análisis pre-trade #{nuevo_id} registrado.")
    print(f"      Mercado: {mercado}")
    print(f"      Edge calculado: {edge_calculado:+.1f}pp  |  Confianza: {nivel_confianza}")
    print(f"      Capital: ${capital_arriesgado:.2f}  |  Sesgos: {', '.join(sesgos_detectados or ['ninguno'])}")
    if not sesgos_controlados and sesgos_detectados:
        print(f"      [!] ATENCION: sesgos detectados y NO marcados como controlados.")
    return nuevo_id


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN 2 — REGISTRO POST-RESOLUCIÓN
# ═══════════════════════════════════════════════════════════════════════════

def registro_post_resolucion(
    registro_id: int,
    resultado: str,                  # "WIN" | "LOSS" | "NULL"
    precio_salida: float,
    capital_inicial: float,
    mi_estimacion_fue: str,          # "CORRECTA" | "INCORRECTA" | "PARCIAL"
    error_cometido: str = "",
    sesgo_que_no_detecte: str = "",
    leccion_aprendida: str = "",
    cambio_protocolo: str = "",
):
    """
    Completa el registro con los datos de resolución.

    Ejemplo:
        registro_post_resolucion(
            registro_id=1,
            resultado="WIN",
            precio_salida=0.98,
            capital_inicial=15.0,
            mi_estimacion_fue="CORRECTA",
            leccion_aprendida="La complejidad SEC del merger xAI fue subestimada...",
            cambio_protocolo="Verificar siempre riesgo regulatorio de fusiones pre-IPO"
        )
    """
    registros = cargar_aprendizaje()
    reg = next((r for r in registros if r.get("id") == registro_id), None)

    if reg is None:
        print(f"  [!] Registro #{registro_id} no encontrado.")
        return

    ganancia = None
    if precio_salida is not None and capital_inicial:
        entrada = reg.get("precio_entrada", 0)
        if entrada > 0:
            shares = capital_inicial / entrada
            ganancia = round((precio_salida - entrada) * shares, 2)

    reg.update({
        "resultado":             resultado,
        "precio_salida":         precio_salida,
        "ganancia_real":         ganancia,
        "mi_estimacion_fue":     mi_estimacion_fue,
        "error_cometido":        error_cometido,
        "sesgo_que_no_detecte":  sesgo_que_no_detecte,
        "leccion_aprendida":     leccion_aprendida,
        "cambio_protocolo":      cambio_protocolo,
        "fecha_resolucion":      datetime.now().strftime("%Y-%m-%d"),
        "fase":                  "COMPLETO",
    })

    guardar_aprendizaje(registros)

    icono = "[G]" if resultado == "WIN" else ("[P]" if resultado == "LOSS" else "[=]")
    print(f"\n  {icono} Registro #{registro_id} completado: {resultado}")
    if ganancia is not None:
        print(f"      Ganancia real: {'+' if ganancia >= 0 else ''}{ganancia:.2f} USD")
    print(f"      Estimación fue: {mi_estimacion_fue}")
    if leccion_aprendida:
        print(f"      Lección: {leccion_aprendida[:80]}")
    if cambio_protocolo:
        print(f"      Cambio protocolo: {cambio_protocolo[:80]}")


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN 3 — ANÁLISIS DE PATRONES DE ERROR
# ═══════════════════════════════════════════════════════════════════════════

def analizar_patrones_error(min_trades: int = 5) -> dict:
    """
    Analiza patrones de error en el historial de aprendizaje.
    Se activa automáticamente cada 10 trades completos.
    Retorna dict con los hallazgos.
    """
    registros  = cargar_aprendizaje()
    completos  = [r for r in registros if r.get("fase") == "COMPLETO"]
    ganas      = [r for r in completos if r.get("resultado") == "WIN"]
    perdidas   = [r for r in completos if r.get("resultado") == "LOSS"]

    titulo("INFORME DE MEJORA PERSONAL")

    if len(completos) < min_trades:
        print(f"\n  Insuficientes trades completos ({len(completos)}/{min_trades} requeridos).")
        print(f"  El informe completo se generará tras {min_trades - len(completos)} trades más.")
        print(f"\n  Trades pre-registrados (sin resolver): {len(registros) - len(completos)}")
        return {}

    sep()
    print(f"\n  Trades analizados: {len(completos)}  ({len(ganas)} wins, {len(perdidas)} losses)\n")

    resultados = {}

    # ── 1. Win rate por tipo de mercado ───────────────────────────────────
    print("  1. WIN RATE POR TIPO DE MERCADO\n")
    mercados_stats = {}
    for r in completos:
        # Extraer categoría del nombre del mercado
        m = r.get("mercado", "")
        cat = "IPO" if "IPO" in m.upper() else (
              "POLITICS" if any(k in m.lower() for k in ("election","iran","trump","war","ceasefire")) else
              "CRYPTO" if any(k in m.lower() for k in ("bitcoin","eth","crypto","btc")) else
              "MACRO" if any(k in m.lower() for k in ("fed","rate","recession","gdp")) else
              "OTRO")
        if cat not in mercados_stats:
            mercados_stats[cat] = {"wins": 0, "total": 0}
        mercados_stats[cat]["total"] += 1
        if r.get("resultado") == "WIN":
            mercados_stats[cat]["wins"] += 1

    for cat, stats in sorted(mercados_stats.items()):
        wr = stats["wins"] / stats["total"] * 100 if stats["total"] else 0
        barra = "█" * int(wr / 5) + "░" * (20 - int(wr / 5))
        print(f"    {cat:10s}: [{barra}] {wr:.0f}%  (n={stats['total']})")
    resultados["win_rate_por_categoria"] = mercados_stats

    # ── 2. Sesgos más frecuentes ──────────────────────────────────────────
    print("\n  2. SESGOS MÁS FRECUENTES\n")
    todos_sesgos = []
    sesgos_en_perdidas = []
    for r in completos:
        sesgos = r.get("sesgos_detectados", [])
        todos_sesgos.extend(sesgos)
        if r.get("resultado") == "LOSS":
            sesgos_en_perdidas.extend(sesgos)
        # Sesgos no detectados
        snd = r.get("sesgo_que_no_detecte", "")
        if snd:
            sesgos_en_perdidas.append(f"{snd} [no detectado]")

    freq_general = Counter(todos_sesgos).most_common(5)
    freq_perdidas = Counter(sesgos_en_perdidas).most_common(3)

    if freq_general:
        for sesgo, n in freq_general:
            print(f"    {sesgo:30s}: {n}x en total")
    else:
        print("    Sin datos de sesgos registrados todavía.")

    if freq_perdidas:
        print("\n    En trades perdidos específicamente:")
        for sesgo, n in freq_perdidas:
            print(f"    [!] {sesgo:30s}: {n}x")
    resultados["sesgos_frecuentes"] = freq_general

    # ── 3. Calibración: edge estimado vs real ─────────────────────────────
    print("\n  3. CALIBRACION — EDGE ESTIMADO VS REAL\n")
    con_edge = [r for r in completos if r.get("edge_calculado_pp") is not None
                and r.get("resultado") in ("WIN", "LOSS")]
    if con_edge:
        edge_est_prom = sum(r["edge_calculado_pp"] for r in con_edge) / len(con_edge)
        # Edge real: 1=WIN, 0=LOSS vs prob_mercado
        edges_reales = []
        for r in con_edge:
            res_bin = 1 if r["resultado"] == "WIN" else 0
            pm = r.get("precio_mercado", 0.5)
            edges_reales.append((res_bin - pm) * 100)
        edge_real_prom = sum(edges_reales) / len(edges_reales)
        error_medio = edge_real_prom - edge_est_prom

        print(f"    Edge estimado promedio : {edge_est_prom:+.1f}pp")
        print(f"    Edge real promedio     : {edge_real_prom:+.1f}pp")
        print(f"    Error sistemático      : {error_medio:+.1f}pp  ", end="")
        if error_medio > 5:
            print("→ Eres sistemáticamente PESIMISTA (subestimas edge real)")
        elif error_medio < -5:
            print("→ Eres sistemáticamente OPTIMISTA (sobreestimas edge)")
        else:
            print("→ Sin sesgo sistemático relevante")
        resultados["error_medio_pp"] = round(error_medio, 2)
    else:
        print("    Insuficientes datos para análisis de calibración.")

    # ── 4. Índice de estrés y rendimiento ─────────────────────────────────
    print("\n  4. ESTRES ALTO vs BAJO — IMPACTO EN RESULTADOS\n")
    alto_estres = [r for r in completos if (r.get("indice_estres_momento") or 0) >= 50]
    bajo_estres = [r for r in completos if (r.get("indice_estres_momento") or 0) < 50]

    def wr_grupo(grupo):
        if not grupo:
            return None
        return sum(1 for r in grupo if r.get("resultado") == "WIN") / len(grupo) * 100

    wr_alto = wr_grupo(alto_estres)
    wr_bajo = wr_grupo(bajo_estres)

    if wr_alto is not None:
        print(f"    Trades con estrés ≥50: {len(alto_estres)} trades  |  Win rate: {wr_alto:.0f}%")
    if wr_bajo is not None:
        print(f"    Trades con estrés <50: {len(bajo_estres)} trades  |  Win rate: {wr_bajo:.0f}%")
    if wr_alto is not None and wr_bajo is not None:
        if wr_bajo > wr_alto + 10:
            print(f"\n    [!] Tomas PEORES decisiones con estrés alto ({wr_alto:.0f}% vs {wr_bajo:.0f}%)")
        else:
            print(f"\n    [OK] El estrés no parece afectar significativamente tus resultados.")
    resultados["impacto_estres"] = {"alto": wr_alto, "bajo": wr_bajo}

    # ── 5. Fuentes con mejor predicción ───────────────────────────────────
    print("\n  5. FUENTES MAS PREDICTIVAS\n")
    fuentes_wins = Counter()
    fuentes_total = Counter()
    for r in completos:
        for f in r.get("fuentes_usadas", []):
            fuentes_total[f] += 1
            if r.get("resultado") == "WIN":
                fuentes_wins[f] += 1

    fuentes_wr = {f: fuentes_wins[f] / fuentes_total[f] * 100
                  for f in fuentes_total if fuentes_total[f] >= 2}
    for f, wr in sorted(fuentes_wr.items(), key=lambda x: -x[1])[:5]:
        print(f"    {f:35s}: {wr:.0f}% win rate (n={fuentes_total[f]})")
    if not fuentes_wr:
        print("    Insuficientes datos (necesitas al menos 2 trades con cada fuente).")
    resultados["fuentes_wr"] = fuentes_wr

    # ── Recomendaciones ───────────────────────────────────────────────────
    print("\n  RECOMENDACIONES BASADAS EN TUS ERRORES REALES\n")
    sep()
    recs = []

    # Win rate bajo
    total_wr = len(ganas) / len(completos) * 100 if completos else 0
    if total_wr < 40:
        recs.append("Win rate < 40%. Revisa si el edge estimado es real antes de entrar.")
    # Estrés
    if wr_alto is not None and wr_bajo is not None and wr_bajo > wr_alto + 10:
        recs.append("Evitar trades cuando índice de estrés ≥ 50. Tu tasa de acierto cae.")
    # Sesgos no controlados
    sin_control = [r for r in completos if r.get("sesgos_detectados") and not r.get("sesgos_controlados")]
    if len(sin_control) > len(completos) * 0.3:
        recs.append("> 30% de trades con sesgos sin controlar. Completar checklist antes de operar.")
    # Edge estimado
    error = resultados.get("error_medio_pp")
    if error is not None and error < -5:
        recs.append(f"Sobreestimas el edge en {abs(error):.1f}pp de media. Sé más conservador.")
    # Fuentes
    for r in perdidas:
        if len(r.get("fuentes_usadas", [])) < 2:
            recs.append("Varios trades perdidos con < 2 fuentes. Nunca entrar sin 2 fuentes A/B.")
            break

    if not recs:
        recs.append("Sin patrones problemáticos claros. Continúa con el protocolo actual.")

    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec}")

    print()
    resultados["recomendaciones"] = recs
    return resultados


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN 4 — SIMULACIÓN MONTE CARLO
# ═══════════════════════════════════════════════════════════════════════════

def simulacion_montecarlo(
    prob_exito: float,
    capital: float,
    precio_entrada: float,
    n_simulaciones: int = 1000,
    n_trades_consecutivos: int = 20,
) -> dict:
    """
    Simula N trades similares con tu probabilidad estimada.
    Muestra escenarios de pérdida, drawdown máximo y riesgo de ruina.

    Parámetros:
        prob_exito      : tu probabilidad estimada de ganar este trade (0-1)
        capital         : capital disponible para este tipo de trade
        precio_entrada  : precio de compra del token (0-1)
        n_simulaciones  : número de simulaciones (default 1000)
        n_trades_consecutivos : cuántos trades similares simular en secuencia

    Ejemplo:
        simulacion_montecarlo(prob_exito=0.25, capital=15.0,
                              precio_entrada=0.09)
    """
    titulo("SIMULACION MONTE CARLO")

    payout = (1 - precio_entrada) / precio_entrada   # ratio ganancia/perdida
    prob_fallo = 1 - prob_exito

    print(f"\n  Parametros:")
    print(f"    Prob. de ganar (tuya)  : {prob_exito:.0%}")
    print(f"    Prob. de perder        : {prob_fallo:.0%}")
    print(f"    Precio entrada         : {precio_entrada:.2f}c")
    print(f"    Payout si ganas        : {payout:.2f}x")
    print(f"    Capital por trade      : ${capital:.2f}")
    print(f"    Trades simulados       : {n_trades_consecutivos}")
    print(f"    Simulaciones           : {n_simulaciones:,}")

    sep()

    perdidas_totales = 0
    max_consecutivos_perdidos = []
    drawdowns = []
    ganancias_finales = []

    for _ in range(n_simulaciones):
        saldo = capital * n_trades_consecutivos  # capital acumulado inicial
        consecutivos_perdidos = 0
        max_consec = 0
        peak = saldo
        min_valley = saldo
        apuesta = capital  # apostamos capital fijo por trade

        for _ in range(n_trades_consecutivos):
            if random.random() < prob_exito:
                saldo += apuesta * payout
                consecutivos_perdidos = 0
            else:
                saldo -= apuesta
                consecutivos_perdidos += 1
                max_consec = max(max_consec, consecutivos_perdidos)

            if saldo > peak:
                peak = saldo
            min_valley = min(min_valley, saldo)

        max_consecutivos_perdidos.append(max_consec)
        drawdown = (peak - min_valley) / peak * 100 if peak > 0 else 0
        drawdowns.append(drawdown)

        ganancia_final_pct = (saldo - capital * n_trades_consecutivos) / (capital * n_trades_consecutivos) * 100
        ganancias_finales.append(ganancia_final_pct)

        if saldo < capital * n_trades_consecutivos:   # terminó perdiendo
            perdidas_totales += 1

    # Estadísticas
    pct_pierde = perdidas_totales / n_simulaciones * 100
    pct_gana   = 100 - pct_pierde
    avg_max_consec = sum(max_consecutivos_perdidos) / n_simulaciones
    p95_consec     = sorted(max_consecutivos_perdidos)[int(0.95 * n_simulaciones)]
    avg_drawdown   = sum(drawdowns) / n_simulaciones
    p95_drawdown   = sorted(drawdowns)[int(0.95 * n_simulaciones)]
    ganancia_media = sum(ganancias_finales) / n_simulaciones
    p5_ganancia    = sorted(ganancias_finales)[int(0.05 * n_simulaciones)]  # peor 5%

    print(f"\n  RESULTADOS (tras {n_trades_consecutivos} trades similares):\n")
    print(f"    Simulaciones en positivo : {pct_gana:.1f}%")
    print(f"    Simulaciones en negativo : {pct_pierde:.1f}%")
    print(f"    Ganancia media esperada  : {ganancia_media:+.1f}% del capital comprometido")
    print(f"    Peor 5% de escenarios    : {p5_ganancia:+.1f}%")

    sep("─", 40)
    print(f"\n  RACHAS PERDEDORAS:\n")
    print(f"    Media de racha máx perdedora  : {avg_max_consec:.1f} trades")
    print(f"    Peor racha (percentil 95)      : {p95_consec} trades consecutivos perdidos")
    print(f"\n  Con una probabilidad de {prob_fallo:.0%} de perder,")
    print(f"  en {n_simulaciones} simulaciones el peor 5% incluía rachas de {p95_consec}+ pérdidas")
    print(f"  consecutivas.")

    sep("─", 40)
    print(f"\n  DRAWDOWN (caída desde máximo):\n")
    print(f"    Drawdown medio   : {avg_drawdown:.1f}%")
    print(f"    Drawdown P95     : {p95_drawdown:.1f}%")

    # Valor Esperado por trade
    ev = prob_exito * capital * payout - prob_fallo * capital
    print(f"\n  VALOR ESPERADO por trade: {'+' if ev >= 0 else ''}{ev:.2f} USD")
    if ev > 0:
        print(f"  [OK] EV positivo — apostar tiene sentido matemáticamente.")
    else:
        print(f"  [!] EV negativo — NO apostar aunque el ratio sea atractivo.")

    print()
    return {
        "pct_pierde": round(pct_pierde, 1),
        "ganancia_media_pct": round(ganancia_media, 1),
        "racha_max_p95": p95_consec,
        "drawdown_p95": round(p95_drawdown, 1),
        "ev_por_trade": round(ev, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN 5 — DETECTOR DE ERRORES SISTÉMICOS
# ═══════════════════════════════════════════════════════════════════════════

def detectar_errores_sistemicos(ultimos_n: int = 5) -> dict:
    """
    Compara el análisis actual con los últimos N análisis para detectar
    loops de confirmación, dependencia de fuente única y optimism bias.
    """
    registros = cargar_aprendizaje()
    ultimos   = registros[-ultimos_n:] if len(registros) >= ultimos_n else registros

    titulo("DETECTOR DE ERRORES SISTEMICOS")

    if len(ultimos) < 2:
        print(f"\n  Insuficientes análisis previos ({len(ultimos)}/{ultimos_n} requeridos).")
        print("  Registra más análisis pre-trade para activar el detector.")
        return {}

    sep()
    print(f"\n  Analizando los últimos {len(ultimos)} registros...\n")
    alertas = []

    # ── 1. Confirmation loop ──────────────────────────────────────────────
    razonamientos = [r.get("razonamiento_principal", "") for r in ultimos if r.get("razonamiento_principal")]
    if len(razonamientos) >= 3:
        # Detectar frases repetidas (ventana deslizante de palabras clave)
        palabras_freq = Counter()
        for texto in razonamientos:
            palabras = set(texto.lower().split())
            palabras_freq.update(palabras)
        palabras_repetidas = [(p, n) for p, n in palabras_freq.most_common(10)
                              if n >= len(razonamientos) - 1 and len(p) > 5]
        if palabras_repetidas:
            alertas.append({
                "tipo": "CONFIRMATION_LOOP",
                "nivel": "AMARILLO",
                "msg": f"Frases repetidas en {len(razonamientos)} análisis seguidos: "
                       f"{', '.join(p for p, _ in palabras_repetidas[:3])}",
                "accion": "¿Tienes nueva evidencia o estás justificando la misma tesis?"
            })

    # ── 2. Dependencia de fuente única ────────────────────────────────────
    fuentes_counts = Counter()
    for r in ultimos:
        for f in r.get("fuentes_usadas", []):
            fuentes_counts[f] += 1

    for fuente, n in fuentes_counts.most_common(3):
        if n >= len(ultimos) - 1:
            alertas.append({
                "tipo": "FUENTE_UNICA",
                "nivel": "ROJO",
                "msg": f"Fuente '{fuente}' usada en {n}/{len(ultimos)} análisis consecutivos.",
                "accion": "Busca al menos 1 fuente alternativa independiente."
            })

    # ── 3. Optimism bias en edge estimado ─────────────────────────────────
    completos = [r for r in ultimos if r.get("fase") == "COMPLETO" and
                 r.get("edge_calculado_pp") is not None and r.get("resultado") is not None]
    if len(completos) >= 3:
        errores = []
        for r in completos:
            res_bin = 1 if r["resultado"] == "WIN" else 0
            pm = r.get("precio_mercado", 0.5)
            edge_real = (res_bin - pm) * 100
            errores.append(edge_real - r["edge_calculado_pp"])

        error_medio = sum(errores) / len(errores)
        if error_medio < -8:
            alertas.append({
                "tipo": "OPTIMISM_BIAS",
                "nivel": "ROJO",
                "msg": f"Sobreestimas el edge en {abs(error_medio):.1f}pp de media "
                       f"(últimos {len(completos)} trades).",
                "accion": "Reduce tu edge estimado en ~10pp antes de la próxima apuesta."
            })
        elif error_medio > 8:
            alertas.append({
                "tipo": "PESSIMISM_BIAS",
                "nivel": "AMARILLO",
                "msg": f"Subestimas el edge en {error_medio:.1f}pp de media.",
                "accion": "Tu análisis es más conservador de lo necesario. Confía más."
            })

    # ── 4. Confianza siempre alta ─────────────────────────────────────────
    siempre_alto = all(r.get("nivel_confianza") == "ALTO" for r in ultimos)
    if siempre_alto and len(ultimos) >= 3:
        alertas.append({
            "tipo": "OVERCONFIDENCE_PATTERN",
            "nivel": "AMARILLO",
            "msg": f"Nivel de confianza 'ALTO' en todos los últimos {len(ultimos)} análisis.",
            "accion": "La mayoría de análisis deberían ser MEDIO. Revisa si eres objetivo."
        })

    # ── 5. Sesgos sin controlar ───────────────────────────────────────────
    sin_ctrl = [r for r in ultimos if r.get("sesgos_detectados") and not r.get("sesgos_controlados")]
    if len(sin_ctrl) >= 2:
        alertas.append({
            "tipo": "SESGOS_SIN_CONTROLAR",
            "nivel": "ROJO",
            "msg": f"{len(sin_ctrl)}/{len(ultimos)} análisis recientes con sesgos sin controlar.",
            "accion": "Marcar sesgos como controlados SOLO si has tomado acción específica."
        })

    # ── Mostrar resultado ─────────────────────────────────────────────────
    if not alertas:
        print("  [OK] Sin errores sistémicos detectados en los últimos análisis.")
        print("  Continúa con el protocolo actual.")
    else:
        iconos = {"ROJO": "[X]", "AMARILLO": "[~]"}
        rojos    = [a for a in alertas if a["nivel"] == "ROJO"]
        amarillos = [a for a in alertas if a["nivel"] == "AMARILLO"]

        if rojos:
            print(f"  ERRORES CRITICOS DETECTADOS ({len(rojos)}):\n")
            for a in rojos:
                print(f"  [X] {a['tipo']}")
                print(f"      {a['msg']}")
                print(f"      Acción: {a['accion']}\n")

        if amarillos:
            print(f"  ADVERTENCIAS ({len(amarillos)}):\n")
            for a in amarillos:
                print(f"  [~] {a['tipo']}")
                print(f"      {a['msg']}")
                print(f"      Acción: {a['accion']}\n")

    print()
    return {"alertas": alertas}


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: Guardar análisis completo de un trade en aprendizaje.json
# ═══════════════════════════════════════════════════════════════════════════

def guardar_analisis_completo(datos: dict) -> int:
    """
    Guarda directamente un dict de análisis (útil para registros programáticos).
    Retorna el ID asignado.
    """
    registros  = cargar_aprendizaje()
    nuevo_id   = max((r.get("id", 0) for r in registros), default=0) + 1
    datos["id"] = nuevo_id
    datos.setdefault("fase", "PRE")
    datos.setdefault("hora", datetime.now().strftime("%H:%M"))
    registros.append(datos)
    guardar_aprendizaje(registros)
    return nuevo_id


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sistema de aprendizaje continuo")
    parser.add_argument("--informe",   action="store_true", help="Generar informe de mejora personal")
    parser.add_argument("--simular",   action="store_true", help="Simulación Monte Carlo interactiva")
    parser.add_argument("--sistemico", action="store_true", help="Detector de errores sistémicos")
    parser.add_argument("--registro",  action="store_true", help="Registrar análisis pre-trade interactivo")
    args = parser.parse_args()

    if args.informe:
        analizar_patrones_error()

    elif args.simular:
        print("\n  SIMULACION MONTE CARLO — Introduce los parámetros:\n")
        try:
            prob = float(input("  Tu probabilidad de ganar (0-1, ej: 0.25): ").strip())
            cap  = float(input("  Capital por trade (USD, ej: 15): ").strip())
            prec = float(input("  Precio de entrada del token (0-1, ej: 0.09): ").strip())
            simulacion_montecarlo(prob_exito=prob, capital=cap, precio_entrada=prec)
        except (ValueError, KeyboardInterrupt):
            print("\n  Entrada inválida o cancelada.")

    elif args.sistemico:
        detectar_errores_sistemicos()

    elif args.registro:
        print("\n  REGISTRO PRE-TRADE — Introduce los datos:\n")
        try:
            mercado = input("  Nombre del mercado: ").strip()
            precio  = float(input("  Precio de entrada (0-1): ").strip())
            prob    = float(input("  Tu probabilidad estimada (0-1): ").strip())
            capital = float(input("  Capital a arriesgar (USD): ").strip())
            estres  = int(input("  Índice de estrés actual (0-100): ").strip())
            fuentes = input("  Fuentes (separadas por coma): ").strip().split(",")
            conf    = input("  Nivel confianza (ALTO/MEDIO/BAJO): ").strip().upper()
            razon   = input("  Razonamiento principal (1 frase): ").strip()
            contra  = input("  Mejor argumento en contra: ").strip()
            sesgos  = input("  Sesgos detectados (separados por coma, o vacío): ").strip()
            sesgos_list = [s.strip() for s in sesgos.split(",") if s.strip()]
            ctrl    = input("  ¿Sesgos controlados? (s/n): ").strip().lower() in ("s", "si", "y")

            registro_pre_trade(
                mercado=mercado, precio_entrada=precio,
                mi_probabilidad_estimada=prob, fuentes_usadas=fuentes,
                nivel_confianza=conf, razonamiento_principal=razon,
                mejor_argumento_contrario=contra, capital_arriesgado=capital,
                indice_estres_momento=estres, sesgos_detectados=sesgos_list,
                sesgos_controlados=ctrl,
            )
        except (ValueError, KeyboardInterrupt):
            print("\n  Entrada inválida o cancelada.")

    else:
        # Por defecto: mostrar resumen del archivo
        registros = cargar_aprendizaje()
        completos = [r for r in registros if r.get("fase") == "COMPLETO"]
        pre       = [r for r in registros if r.get("fase") == "PRE"]
        print(f"\n  aprendizaje.json: {len(registros)} registros "
              f"({len(completos)} completos, {len(pre)} pre-trade)")
        if registros:
            ultimo = registros[-1]
            print(f"  Último: #{ultimo.get('id')} — {ultimo.get('mercado','')[:50]} "
                  f"[{ultimo.get('fase','')}]")
        print()
        print("  Comandos disponibles:")
        print("    --informe    Informe de mejora personal")
        print("    --simular    Simulación Monte Carlo")
        print("    --sistemico  Detector de errores sistémicos")
        print("    --registro   Registrar análisis pre-trade")
        print()
