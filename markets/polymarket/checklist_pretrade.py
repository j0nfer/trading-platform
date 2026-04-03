"""
checklist_pretrade.py
Checklist obligatorio pre-trade con 3 bloques: Analisis, Psicologia, Capital.
Uso:
  python checklist_pretrade.py                  -- interactivo
  python checklist_pretrade.py --mercado "X"    -- con nombre del mercado
"""
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LOG_FILE       = Path(__file__).parent / "checklist_log.json"
PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"
CAPITAL_TOTAL  = 434.24
RESERVA_MIN_PCT = 0.20   # 20% siempre intocable

# ═══════════════════════════════════════════════════════════════════════════
# DEFINICION DEL CHECKLIST
# ═══════════════════════════════════════════════════════════════════════════

BLOQUE_A = [
    {
        "id":      "A1",
        "texto":   "Tienes al menos 2 fuentes nivel A o B independientes que soporten tu tesis?",
        "tipo":    "SI",   # respuesta requerida para aprobar
        "peso":    "CRITICO",
        "fallo_msg": "Minimo 2 fuentes A/B independientes. Una sola fuente = no entrar.",
    },
    {
        "id":      "A2",
        "texto":   "Has leido y puedes escribir el mejor argumento en CONTRA de tu posicion?",
        "tipo":    "SI",
        "peso":    "CRITICO",
        "fallo_msg": "Sin conocer el argumento contrario, el analisis esta incompleto.",
    },
    {
        "id":      "A3",
        "texto":   "Las reglas exactas de resolucion del mercado son claras y sin ambiguedad?",
        "tipo":    "SI",
        "peso":    "CRITICO",
        "fallo_msg": "Ambiguedad de resolucion = riesgo de perder aunque 'tengas razon'.",
    },
    {
        "id":      "A4",
        "texto":   "El edge calculado es mayor de +8pp (prob propia vs precio mercado)?",
        "tipo":    "SI",
        "peso":    "CRITICO",
        "fallo_msg": "Edge < 8pp no justifica el riesgo despues de fees y spread.",
    },
    {
        "id":      "A5",
        "texto":   "El volumen del mercado es mayor de $500.000?",
        "tipo":    "SI",
        "peso":    "CRITICO",
        "fallo_msg": "Volumen bajo = precio manipulable = edge falso.",
    },
]

BLOQUE_B = [
    {
        "id":      "B1",
        "texto":   "Encontraste este mercado hace menos de 2 horas?",
        "tipo":    "NO",   # respuesta requerida para aprobar: NO
        "peso":    "ROJO",
        "fallo_msg": "Precipitacion. Espera 24h y vuelve a analizar.",
    },
    {
        "id":      "B2",
        "texto":   "El precio de este mercado subio mas de 15pp hoy?",
        "tipo":    "NO",
        "peso":    "ROJO",
        "fallo_msg": "Señal clara de FOMO. Si el precio no hubiera subido, habrias entrado?",
    },
    {
        "id":      "B3",
        "texto":   "Lo recomendo alguien en redes sociales, Telegram, Twitter u otro canal?",
        "tipo":    "NO",
        "peso":    "ROJO",
        "fallo_msg": "Efecto manada. Haz analisis independiente desde cero antes de proceder.",
    },
    {
        "id":      "B4",
        "texto":   "Llevas mas de 30 minutos mirando este mercado sin tomar decision?",
        "tipo":    "NO",
        "peso":    "AMARILLO",
        "fallo_msg": "Obsesion/ansiedad detectada. Toma distancia y vuelve en 2 horas.",
    },
    {
        "id":      "B5",
        "texto":   "Has tenido una perdida significativa en las ultimas 48 horas?",
        "tipo":    "NO",
        "peso":    "ROJO",
        "fallo_msg": "Riesgo de revenge trading. Espera 48h completas tras una perdida.",
    },
]

BLOQUE_C = [
    {
        "id":      "C1",
        "texto":   "Tienes suficiente cash sin comprometer la reserva minima del 20% del portfolio?",
        "tipo":    "SI",
        "peso":    "CRITICO",
        "fallo_msg": f"Reserva minima obligatoria: ${CAPITAL_TOTAL * RESERVA_MIN_PCT:.2f} siempre intocables.",
    },
    {
        "id":      "C2",
        "texto":   "El capital en este trade es menos del 15% del portfolio total ($65.14)?",
        "tipo":    "SI",
        "peso":    "CRITICO",
        "fallo_msg": "Concentracion excesiva. Maximo 15% por posicion ($65.14 con capital actual).",
    },
    {
        "id":      "C3",
        "texto":   "Puedes permitirte perder todo este capital sin afectar gastos de vida?",
        "tipo":    "SI",
        "peso":    "CRITICO",
        "fallo_msg": "Nunca operar con capital que no puedes permitirte perder.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# LOGICA DEL CHECKLIST
# ═══════════════════════════════════════════════════════════════════════════

def sep(char="─", ancho=66):
    print(char * ancho)

def preguntar_si_no(texto, default=None):
    while True:
        r = input(f"\n  {'[SI requerido]' if default is None else ''} {texto}\n  > ").strip().lower()
        if r in ("s", "si", "sí", "y", "yes", "1"):
            return True
        if r in ("n", "no", "0"):
            return False
        print("  Responde s (si) o n (no)")

def evaluar_bloque(preguntas, respuestas):
    fallos     = []
    advertencias = []
    for p in preguntas:
        resp = respuestas.get(p["id"])
        if resp is None:
            continue
        respuesta_ok = (p["tipo"] == "SI" and resp) or (p["tipo"] == "NO" and not resp)
        if not respuesta_ok:
            entry = {
                "id":     p["id"],
                "texto":  p["texto"],
                "peso":   p["peso"],
                "fallo":  p["fallo_msg"],
            }
            if p["peso"] in ("CRITICO", "ROJO"):
                fallos.append(entry)
            else:
                advertencias.append(entry)
    return fallos, advertencias

def calcular_resultado(fallos_a, fallos_b, fallos_c, adv_a, adv_b, adv_c):
    total_fallos = fallos_a + fallos_b + fallos_c
    total_adv    = adv_a + adv_b + adv_c

    # Cualquier rojo en Bloque B = NO ENTRAR HOY
    if fallos_b:
        return "NO_ENTRAR", "ROJO"
    # Criticos en A o C = NO ENTRAR
    if fallos_a or fallos_c:
        return "NO_ENTRAR", "ROJO"
    # 1-2 advertencias = ESPERAR 24h
    if len(total_adv) >= 1:
        return "ESPERAR_24H", "AMARILLO"
    return "PROCEDER", "VERDE"


def ejecutar_checklist(mercado="", interactivo=True, respuestas_pre=None):
    """
    Ejecuta el checklist pre-trade.

    Si interactivo=True: pregunta al usuario.
    Si interactivo=False: usa respuestas_pre (dict de id→bool).
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("=" * 66)
    print(f"  CHECKLIST PRE-TRADE — {ahora}")
    if mercado:
        print(f"  Mercado: {mercado[:60]}")
    print("=" * 66)

    respuestas = {}

    def hacer_pregunta(p, bloque_letra):
        if not interactivo and respuestas_pre:
            resp = respuestas_pre.get(p["id"])
            respuestas[p["id"]] = resp if resp is not None else (p["tipo"] == "SI")
            return

        marcador = "[SI req]" if p["tipo"] == "SI" else "[NO req]"
        peso_ico = "[!!!]" if p["peso"] in ("CRITICO", "ROJO") else "[ ~ ]"
        respuestas[p["id"]] = preguntar_si_no(
            f"{peso_ico} {marcador} {p['texto']}"
        )

    # BLOQUE A
    print("\n  BLOQUE A — ANALISIS  (todas deben ser SI)\n")
    sep()
    for p in BLOQUE_A:
        hacer_pregunta(p, "A")

    # BLOQUE B
    print("\n\n  BLOQUE B — PSICOLOGIA  (todas deben ser NO)\n")
    sep()
    for p in BLOQUE_B:
        hacer_pregunta(p, "B")

    # BLOQUE C
    print("\n\n  BLOQUE C — CAPITAL  (todas deben ser SI)\n")
    sep()
    for p in BLOQUE_C:
        hacer_pregunta(p, "C")

    # Evaluar
    fallos_a, adv_a = evaluar_bloque(BLOQUE_A, respuestas)
    fallos_b, adv_b = evaluar_bloque(BLOQUE_B, respuestas)
    fallos_c, adv_c = evaluar_bloque(BLOQUE_C, respuestas)
    resultado, color = calcular_resultado(fallos_a, fallos_b, fallos_c, adv_a, adv_b, adv_c)

    # Mostrar resultado
    iconos = {"VERDE": "[V] PROCEDER", "AMARILLO": "[~] ESPERAR 24H", "ROJO": "[X] NO ENTRAR HOY"}
    print("\n\n" + "=" * 66)
    print(f"  RESULTADO: {iconos[color]}")
    print("=" * 66)

    todos_fallos = fallos_a + fallos_b + fallos_c + adv_a + adv_b + adv_c
    if todos_fallos:
        print(f"\n  Motivos:\n")
        for f in todos_fallos:
            icono = "[X]" if f["peso"] in ("CRITICO", "ROJO") else "[~]"
            print(f"  {icono} [{f['id']}] {f['fallo']}")

    if resultado == "PROCEDER":
        print("\n  Todos los criterios cumplidos.")
        print("  Recuerda: documentar en diario.json ANTES de ejecutar.")
        print(f"  Limite capital max: ${CAPITAL_TOTAL * 0.15:.2f} (15% portfolio)")

    elif resultado == "ESPERAR_24H":
        print("\n  Espera 24 horas y repite el checklist.")
        print("  Si al dia siguiente sigue siendo buena idea -> proceder.")

    elif resultado == "NO_ENTRAR":
        print("\n  No abrir ninguna posicion nueva hoy.")
        if fallos_b:
            print("  Motivo principal: sesgo psicologico activo (Bloque B).")
        print("  Revisa el analisis completo manana con la mente fria.")

    # Log
    entrada_log = {
        "timestamp":  ahora,
        "mercado":    mercado,
        "respuestas": respuestas,
        "fallos":     [f["id"] for f in fallos_a + fallos_b + fallos_c],
        "advertencias": [a["id"] for a in adv_a + adv_b + adv_c],
        "resultado":  resultado,
        "color":      color,
    }
    guardar_log(entrada_log)

    return {
        "resultado":  resultado,
        "color":      color,
        "fallos":     fallos_a + fallos_b + fallos_c,
        "advertencias": adv_a + adv_b + adv_c,
    }


# ═══════════════════════════════════════════════════════════════════════════
# LOG
# ═══════════════════════════════════════════════════════════════════════════

def guardar_log(entrada):
    historial = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                historial = json.load(f)
        except Exception:
            historial = []
    historial.append(entrada)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

def mostrar_historial_checklist(n=10):
    if not LOG_FILE.exists():
        print("  Sin registros de checklist todavia.")
        return
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            historial = json.load(f)
    except Exception:
        print("  Error leyendo log.")
        return

    print(f"\n  Ultimos {min(n, len(historial))} checklists:\n")
    sep()
    for entry in historial[-n:]:
        iconos = {"VERDE": "[V]", "AMARILLO": "[~]", "ROJO": "[X]"}
        icono  = iconos.get(entry["color"], "[?]")
        print(f"  {icono} {entry['timestamp']}  |  {entry['resultado']:15s}  |  {entry['mercado'][:40]}")
        if entry.get("fallos"):
            print(f"       Fallos: {', '.join(entry['fallos'])}")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Checklist pre-trade obligatorio")
    parser.add_argument("--mercado",   default="", help="Nombre del mercado a analizar")
    parser.add_argument("--historial", action="store_true", help="Ver historial de checklists")
    args = parser.parse_args()

    if args.historial:
        mostrar_historial_checklist()
    else:
        ejecutar_checklist(mercado=args.mercado, interactivo=True)
