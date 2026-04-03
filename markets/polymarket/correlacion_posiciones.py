# -*- coding: utf-8 -*-
"""
correlacion_posiciones.py — Calculador de correlación entre posiciones Polymarket

Calcula correlación lógica entre posiciones abiertas y alerta si se añade
una nueva posición que eleve la concentración de riesgo por encima del 60%.

USO:
  python correlacion_posiciones.py              # Análisis del portfolio actual
  python correlacion_posiciones.py --nueva      # Evaluar correlación de nueva posición
  python correlacion_posiciones.py --escenarios # Mostrar todos los escenarios
  python correlacion_posiciones.py --rec        # Recomendaciones de diversificación
"""

import sys
import io
import json
import os
import itertools
import requests
from datetime import datetime

# Forzar UTF-8 en Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TRADING_DIR    = os.environ.get("TRADING_DIR", "C:\\inversiones")
GAMMA_API      = "https://gamma-api.polymarket.com"
PORTFOLIO_JSON = os.path.join(TRADING_DIR, "portfolio.json")


def _leer_capitales_portfolio() -> dict:
    """Lee capitales reales desde portfolio.json. Fallback a hardcoded si falla."""
    defaults = {"P1_Apr15_NO": 200.0, "P2_Jun30_NO": 134.0}
    try:
        with open(PORTFOLIO_JSON, encoding="utf-8") as f:
            data = json.load(f)
        posiciones = data.get("posiciones_polymarket", [])
        result = {}
        for pos in posiciones:
            pid = pos.get("id", "")
            entrada = pos.get("precio_entrada_avg", 0)
            shares  = pos.get("shares", 0)
            if pid == "P1_Apr15_NO":
                result["P1_Apr15_NO"] = round(entrada * shares, 2)
            elif pid == "P2_Jun30_NO":
                result["P2_Jun30_NO"] = round(entrada * shares, 2)
        return result if result else defaults
    except Exception:
        return defaults

# ─── Definición de posiciones ─────────────────────────────────────────────────
# Cada posición tiene escenarios que la hacen GANAR (+1) o PERDER (-1)

POSICIONES = {
    "P1_Apr15_NO": {
        "nombre": "Ceasefire Apr15 — NO",
        "descripcion": "US x Iran ceasefire by April 15",
        "direccion": "NO",
        "entrada": 0.657,
        "shares": 304.3,
        "capital": 200.0,
        "resuelve": "2026-04-15",
        "escenarios": {
            # (nombre_escenario): resultado (+1=gana, -1=pierde, 0=neutro)
            "ceasefire_antes_apr15":     -1,
            "conflicto_continua_apr15":  +1,
            "escalada_militar":          +1,
            "tregua_temporal_no_formal": +1,
            "deal_secreto_oman":         -1,
            "trump_taco_trade":          -1,
            "ataque_nuclear":            +1,
            "nuevos_strikes_iran":       +1,
            "brent_cae_10pct":           -1,
            "hormuz_reabre":             -1,
        }
    },
    "P2_Jun30_NO": {
        "nombre": "Conflict Jun30 — NO",
        "descripcion": "Iran x Israel/US conflict ends by June 30",
        "direccion": "NO",
        "entrada": 0.24,
        "shares": 558.8,
        "capital": 134.0,
        "resuelve": "2026-06-30",
        "escenarios": {
            "ceasefire_antes_apr15":     -1,  # ceasefire = conflict ends
            "conflicto_continua_apr15":  +1,
            "escalada_militar":          +1,
            "tregua_temporal_no_formal": 0,   # tregua temporal ≠ fin de conflicto (ambiguo)
            "deal_secreto_oman":         -1,
            "trump_taco_trade":          -1,
            "ataque_nuclear":            +1,
            "nuevos_strikes_iran":       +1,
            "brent_cae_10pct":           -1,
            "hormuz_reabre":             -1,
        }
    },
}

# Base de mercados para recomendaciones de diversificación
MERCADOS_BAJA_CORRELACION = [
    {
        "nombre": "SpaceX IPO before 2027 — NO",
        "slug": "spacex-ipo-before-2027",
        "escenarios": {
            "ceasefire_antes_apr15":     0,   # neutral
            "conflicto_continua_apr15":  -1,  # guerra = IPO difícil → NO gana
            "escalada_militar":          -1,
            "tregua_temporal_no_formal": 0,
            "deal_secreto_oman":         0,
            "trump_taco_trade":          0,
            "ataque_nuclear":            -1,
            "nuevos_strikes_iran":       -1,
            "brent_cae_10pct":           0,
            "hormuz_reabre":             0,
        }
    },
    {
        "nombre": "Fed no cambia tipos Abril — YES",
        "slug": "fed-holds-rates-april-2026",
        "escenarios": {
            "ceasefire_antes_apr15":     0,
            "conflicto_continua_apr15":  +1,  # guerra → Fed pausa
            "escalada_militar":          +1,
            "tregua_temporal_no_formal": 0,
            "deal_secreto_oman":         0,
            "trump_taco_trade":          -1,
            "ataque_nuclear":            +1,
            "nuevos_strikes_iran":       +1,
            "brent_cae_10pct":           -1,
            "hormuz_reabre":             0,
        }
    },
    {
        "nombre": "Warsh confirmed Fed Chair — NO",
        "slug": "warsh-confirmed-fed-chair",
        "escenarios": {
            "ceasefire_antes_apr15":     0,
            "conflicto_continua_apr15":  +1,
            "escalada_militar":          0,
            "tregua_temporal_no_formal": 0,
            "deal_secreto_oman":         0,
            "trump_taco_trade":          0,
            "ataque_nuclear":            0,
            "nuevos_strikes_iran":       0,
            "brent_cae_10pct":           0,
            "hormuz_reabre":             0,
        }
    },
    {
        "nombre": "US recesión 2026 — YES",
        "slug": "us-recession-2026",
        "escenarios": {
            "ceasefire_antes_apr15":     -1,  # paz = recovery
            "conflicto_continua_apr15":  +1,  # guerra → recesión
            "escalada_militar":          +1,
            "tregua_temporal_no_formal": 0,
            "deal_secreto_oman":         -1,
            "trump_taco_trade":          -1,
            "ataque_nuclear":            +1,
            "nuevos_strikes_iran":       +1,
            "brent_cae_10pct":           -1,
            "hormuz_reabre":             +1,
        }
    },
    {
        "nombre": "Bitcoin > $150K en 2026 — YES",
        "slug": "bitcoin-150k-2026",
        "escenarios": {
            "ceasefire_antes_apr15":     +1,
            "conflicto_continua_apr15":  -1,
            "escalada_militar":          -1,
            "tregua_temporal_no_formal": 0,
            "deal_secreto_oman":         +1,
            "trump_taco_trade":          +1,
            "ataque_nuclear":            -1,
            "nuevos_strikes_iran":       -1,
            "brent_cae_10pct":           +1,
            "hormuz_reabre":             +1,
        }
    },
]

DESCRIPCION_ESCENARIOS = {
    "ceasefire_antes_apr15":     "Ceasefire antes de Apr15",
    "conflicto_continua_apr15":  "Conflicto continúa post Apr15",
    "escalada_militar":          "Escalada militar EE.UU./Iran",
    "tregua_temporal_no_formal": "Tregua temporal sin formalizar",
    "deal_secreto_oman":         "Deal secreto vía Omán",
    "trump_taco_trade":          "Trump Taco Trade (retirada)",
    "ataque_nuclear":            "Ataque/amenaza nuclear",
    "nuevos_strikes_iran":       "Nuevos strikes EE.UU. a Irán",
    "brent_cae_10pct":           "Brent cae >10% en 1 semana",
    "hormuz_reabre":             "Estrecho de Hormuz reabre",
}

# ─── Cálculo de correlación ───────────────────────────────────────────────────

def calcular_correlacion(escenarios_a: dict, escenarios_b: dict) -> float:
    """
    Calcula correlación lógica entre dos posiciones.
    +1.0 = perfectamente correlacionadas (siempre ganan/pierden juntas)
    -1.0 = perfectamente anticorrelacionadas (hedge perfecto)
    0.0 = sin correlación
    """
    escenarios = set(escenarios_a.keys()) | set(escenarios_b.keys())
    acuerdos  = 0
    desacuerdos = 0
    neutros = 0

    for esc in escenarios:
        a = escenarios_a.get(esc, 0)
        b = escenarios_b.get(esc, 0)
        if a == 0 or b == 0:
            neutros += 1
            continue
        if a == b:
            acuerdos += 1
        else:
            desacuerdos += 1

    total = acuerdos + desacuerdos
    if total == 0:
        return 0.0
    return round((acuerdos - desacuerdos) / total, 3)


def clasificar_correlacion(corr: float) -> str:
    if corr >= 0.8:
        return "🔴 MUY ALTA"
    elif corr >= 0.6:
        return "🟠 ALTA"
    elif corr >= 0.3:
        return "🟡 MODERADA"
    elif corr >= -0.3:
        return "🟢 BAJA"
    elif corr >= -0.6:
        return "🔵 NEGATIVA MODERADA (hedge parcial)"
    else:
        return "💜 NEGATIVA ALTA (hedge fuerte)"


def calcular_exposicion_efectiva(posiciones: dict) -> dict:
    """
    Calcula la exposición real considerando correlaciones.
    Posiciones muy correlacionadas cuentan casi como una sola.
    """
    nombres = list(posiciones.keys())
    capitales = {k: v["capital"] for k, v in posiciones.items()}
    capital_total = sum(capitales.values())

    if len(nombres) < 2:
        return {"exposicion_efectiva": capital_total, "diversificacion_real": 0.0}

    # Correlación promedio entre pares
    corrs = []
    for a, b in itertools.combinations(nombres, 2):
        c = calcular_correlacion(
            posiciones[a]["escenarios"],
            posiciones[b]["escenarios"]
        )
        corrs.append(c)

    corr_media = sum(corrs) / len(corrs) if corrs else 0.0
    n = len(nombres)

    # Exposición efectiva = capital_total * sqrt(1/n + (1-1/n)*corr_media)
    import math
    factor_diversif = math.sqrt(1/n + (1 - 1/n) * corr_media)
    exposicion_efectiva = capital_total * factor_diversif

    return {
        "exposicion_efectiva": round(exposicion_efectiva, 2),
        "diversificacion_real": round(1 - factor_diversif, 3),
        "correlacion_media": round(corr_media, 3),
    }


# ─── Análisis de nueva posición ───────────────────────────────────────────────

def evaluar_nueva_posicion(nueva_pos: dict, posiciones_actuales: dict) -> dict:
    """
    Evalúa el impacto de añadir una nueva posición al portfolio.
    """
    resultado = {"correlaciones": {}, "alerta": False, "mensaje": ""}

    for nombre, pos in posiciones_actuales.items():
        corr = calcular_correlacion(nueva_pos["escenarios"], pos["escenarios"])
        resultado["correlaciones"][nombre] = corr

    corr_max = max(resultado["correlaciones"].values(), default=0)

    if corr_max > 0.6:
        resultado["alerta"] = True
        pos_max = max(resultado["correlaciones"], key=resultado["correlaciones"].get)
        resultado["mensaje"] = (
            f"⚠️  ALERTA: La nueva posición tiene correlación {corr_max:.0%} "
            f"con {posiciones_actuales[pos_max]['nombre']}. "
            f"Supera el umbral del 60%. Reconsiderar antes de entrar."
        )
    else:
        resultado["mensaje"] = (
            f"✅ Correlación máxima con portfolio existente: {corr_max:.0%}. "
            f"Dentro del umbral. La posición DIVERSIFICA el portfolio."
        )

    return resultado


# ─── Visualización ────────────────────────────────────────────────────────────

def imprimir_matriz(posiciones: dict, extras: list = None):
    """Imprime la matriz de correlación en formato texto."""
    nombres = list(posiciones.keys())
    labels  = [posiciones[n]["nombre"][:22] for n in nombres]
    extras_labels = []

    if extras:
        for e in extras:
            nombres.append(f"EXTRA_{e['nombre'][:10]}")
            labels.append(f"[?]{e['nombre'][:18]}")

    print("\n  MATRIZ DE CORRELACIÓN")
    print("  " + "─" * 72)

    # Cabecera
    header = "  {:<25}".format("POSICIÓN")
    for i, lbl in enumerate(labels):
        header += f"  {lbl[:15]:>15}"
    print(header)
    print("  " + "─" * 72)

    # Filas
    all_escenarios = (
        {k: v["escenarios"] for k, v in posiciones.items()} |
        {f"EXTRA_{e['nombre'][:10]}": e["escenarios"] for e in (extras or [])}
    )

    for i, nombre_i in enumerate(nombres):
        fila = f"  {labels[i]:<25}"
        esc_i = all_escenarios[nombre_i]
        for j, nombre_j in enumerate(nombres):
            esc_j = all_escenarios[nombre_j]
            if i == j:
                fila += f"  {'100%':>15}"
            else:
                corr = calcular_correlacion(esc_i, esc_j)
                fila += f"  {corr*100:>14.0f}%"
        print(fila)

    print("  " + "─" * 72)


def imprimir_escenarios(posiciones: dict):
    """Muestra cómo cada escenario afecta a las posiciones."""
    nombres = list(posiciones.keys())
    todos_escenarios = set()
    for pos in posiciones.values():
        todos_escenarios.update(pos["escenarios"].keys())

    print("\n  TABLA DE ESCENARIOS")
    print(f"  {'Escenario':<35}", end="")
    for n in nombres:
        print(f"  {posiciones[n]['nombre'][:14]:>14}", end="")
    print()
    print("  " + "─" * (35 + 18 * len(nombres)))

    gana_juntas = 0
    pierde_juntas = 0
    diverge = 0

    for esc in sorted(todos_escenarios):
        resultados = [posiciones[n]["escenarios"].get(esc, 0) for n in nombres]
        desc = DESCRIPCION_ESCENARIOS.get(esc, esc)
        print(f"  {desc:<35}", end="")
        for r in resultados:
            simbolo = "✅ +1" if r == +1 else "❌ -1" if r == -1 else " ○  0"
            print(f"  {simbolo:>14}", end="")
        print()

        activos = [r for r in resultados if r != 0]
        if len(activos) >= 2:
            if all(r == activos[0] for r in activos):
                if activos[0] == +1:
                    gana_juntas += 1
                else:
                    pierde_juntas += 1
            else:
                diverge += 1

    print("  " + "─" * (35 + 18 * len(nombres)))
    print(f"\n  Escenarios donde AMBAS GANAN : {gana_juntas}")
    print(f"  Escenarios donde AMBAS PIERDEN: {pierde_juntas}")
    print(f"  Escenarios DIVERGENTES         : {diverge}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def analisis_completo():
    print(f"\n{'='*60}")
    print(f"  ANÁLISIS DE CORRELACIÓN — PORTFOLIO")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*60}")

    # ── Cargar capitales reales desde portfolio.json ──────────────────────────
    capitales_reales = _leer_capitales_portfolio()
    for pid, cap in capitales_reales.items():
        if pid in POSICIONES:
            POSICIONES[pid]["capital"] = cap

    # ── 1. Matriz de correlación actual ──────────────────────────────────────
    nombres = list(POSICIONES.keys())
    capital_total = sum(p["capital"] for p in POSICIONES.values())

    print(f"\n  POSICIONES ACTUALES:")
    for n, pos in POSICIONES.items():
        print(f"  • {pos['nombre']:<30} Capital: ${pos['capital']:.0f}  "
              f"({pos['capital']/capital_total*100:.0f}%)")

    imprimir_matriz(POSICIONES)

    # ── 2. Correlación par a par ──────────────────────────────────────────────
    print(f"\n  CORRELACIONES PAR A PAR:")
    for a, b in itertools.combinations(nombres, 2):
        corr = calcular_correlacion(
            POSICIONES[a]["escenarios"],
            POSICIONES[b]["escenarios"]
        )
        clase = clasificar_correlacion(corr)
        print(f"  {POSICIONES[a]['nombre'][:22]:22}  ↔  "
              f"{POSICIONES[b]['nombre'][:22]:22}  =  {corr*100:>5.1f}%  {clase}")

    # ── 3. Exposición efectiva ────────────────────────────────────────────────
    expo = calcular_exposicion_efectiva(POSICIONES)
    print(f"\n  EXPOSICIÓN EFECTIVA:")
    print(f"  Capital total invertido : ${capital_total:.2f}")
    print(f"  Exposición efectiva     : ${expo['exposicion_efectiva']:.2f}  "
          f"(como si fuera UNA posición de este tamaño)")
    print(f"  Diversificación real    : {expo['diversificacion_real']*100:.1f}%")
    print(f"  Correlación media       : {expo['correlacion_media']*100:.1f}%")

    if expo["correlacion_media"] > 0.6:
        print(f"\n  🔴 ALERTA REGLA 2: Correlación media {expo['correlacion_media']*100:.0f}% > 60%.")
        print(f"     El portfolio actúa como una sola posición concentrada.")
        print(f"     Riesgo real = {expo['exposicion_efectiva']:.0f}$ de {capital_total:.0f}$ invertidos.")
    else:
        print(f"\n  ✅ Correlación dentro de límites aceptables.")


def analisis_escenarios():
    print(f"\n{'='*60}")
    print(f"  ANÁLISIS DE ESCENARIOS COMPLETO")
    print(f"{'='*60}")
    imprimir_escenarios(POSICIONES)


def recomendaciones_diversificacion():
    print(f"\n{'='*60}")
    print(f"  RECOMENDACIONES DE DIVERSIFICACIÓN")
    print(f"{'='*60}")

    print(f"\n  Mercados con baja correlación con el portfolio actual:\n")

    resultados = []
    for mercado in MERCADOS_BAJA_CORRELACION:
        corrs = {}
        for nombre, pos in POSICIONES.items():
            c = calcular_correlacion(mercado["escenarios"], pos["escenarios"])
            corrs[nombre] = c
        corr_max = max(corrs.values())
        corr_media = sum(corrs.values()) / len(corrs)
        resultados.append({
            "mercado": mercado,
            "corr_max": corr_max,
            "corr_media": corr_media,
            "corrs": corrs
        })

    # Ordenar por correlación media (menor primero = mejor diversificador)
    resultados.sort(key=lambda x: x["corr_media"])

    for i, r in enumerate(resultados, 1):
        m = r["mercado"]
        clase = clasificar_correlacion(r["corr_media"])
        print(f"  {i}. {m['nombre']}")
        for pnombre, c in r["corrs"].items():
            print(f"     ↔ {POSICIONES[pnombre]['nombre'][:30]:30}: {c*100:+.0f}%")
        print(f"     Correlación media: {r['corr_media']*100:+.1f}%  {clase}")
        if r["corr_max"] <= 0.3:
            print(f"     ✅ EXCELENTE diversificador")
        elif r["corr_max"] <= 0.6:
            print(f"     🟡 Diversificador moderado")
        else:
            print(f"     ⚠️  Correlación alta — no diversifica bien")
        print()


def evaluar_interactivo():
    """Modo interactivo para evaluar una nueva posición."""
    print(f"\n{'='*60}")
    print(f"  EVALUAR NUEVA POSICIÓN")
    print(f"{'='*60}\n")
    print("  Indica el nombre del mercado a evaluar:")
    print("  (escribe el nombre o 'lista' para ver opciones predefinidas)\n")
    nombre = input("  > ").strip()

    if nombre.lower() == "lista":
        for i, m in enumerate(MERCADOS_BAJA_CORRELACION, 1):
            print(f"  {i}. {m['nombre']}")
        idx = int(input("\n  Número: ").strip()) - 1
        mercado = MERCADOS_BAJA_CORRELACION[idx]
    else:
        print("\n  Este mercado no está en la base de datos predefinida.")
        print("  Para un análisis preciso, añade sus escenarios al script.")
        return

    resultado = evaluar_nueva_posicion(mercado, POSICIONES)
    print(f"\n  {resultado['mensaje']}\n")
    print("  Correlaciones detalladas:")
    for pos_nombre, corr in resultado["correlaciones"].items():
        clase = clasificar_correlacion(corr)
        print(f"  • {POSICIONES[pos_nombre]['nombre']}: {corr*100:+.1f}%  {clase}")

    if resultado["alerta"]:
        print(f"\n  ⛔ RECOMENDACIÓN: No entrar sin reducir exposición Iran primero.")
    else:
        print(f"\n  ✅ RECOMENDACIÓN: Esta posición mejora la diversificación.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--escenarios":
        analisis_completo()
        analisis_escenarios()
    elif arg == "--rec":
        recomendaciones_diversificacion()
    elif arg == "--nueva":
        analisis_completo()
        evaluar_interactivo()
    else:
        analisis_completo()
        print()
        recomendaciones_diversificacion()
