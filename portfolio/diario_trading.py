# -*- coding: utf-8 -*-
"""
diario_trading.py — Journal Pre-Trade Obligatorio (Regla de Oro #6)
====================================================================
Antes de cualquier trade >$30 USDC, completar este formulario.
Guarda el registro en logs/diario_trading.json

CLI:
  python diario_trading.py --nuevo        → formulario pre-trade interactivo
  python diario_trading.py --historial    → muestra últimas 10 entradas
  python diario_trading.py --checklist    → checklist emocional rapido
"""

import os, sys, io, json, datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE     = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = os.path.join(BASE, "logs")
DIARIO_F = os.path.join(LOG_DIR, "diario_trading.json")

os.makedirs(LOG_DIR, exist_ok=True)

PREGUNTAS_TRADE = [
    ("mercado",         "En que mercado? (nombre o slug)"),
    ("direccion",       "Direccion? (YES/NO)"),
    ("capital",         "Capital a invertir? (en USDC)"),
    ("tesis",           "Cual es tu tesis en 1-2 frases?"),
    ("argumento_contra","Cual es el mejor argumento EN CONTRA de esta apuesta?"),
    ("catalizador",     "Que evento concreto te daria la razon? Y en contra?"),
    ("score_checklist", "Cuanto sacaste en el checklist de CONOCIMIENTO.md? (0-30)"),
    ("estado_emocional","Estado emocional ahora mismo (0=tranquilo, 10=estresado/FOMO)"),
]

CHECKLIST_EMOCIONAL = [
    "Llevas mas de 6 horas de sueno? (s/n)",
    "Ha pasado mas de 48h desde tu ultima perdida significativa? (s/n)",
    "El precio subio mas de 15pp HOY? (s/n — si si, posible FOMO)",
    "Estas tomando esta decision con calma, sin urgencia? (s/n)",
    "Tienes al menos 2 fuentes A/B que confirman tu tesis? (s/n)",
]

def cargar_diario():
    if os.path.exists(DIARIO_F):
        with open(DIARIO_F, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def guardar_diario(entradas):
    with open(DIARIO_F, "w", encoding="utf-8") as f:
        json.dump(entradas, f, indent=2, ensure_ascii=False)

def checklist_emocional():
    print("\n" + "="*50)
    print("  CHECKLIST EMOCIONAL — Regla 7")
    print("="*50)
    advertencias = []
    for i, pregunta in enumerate(CHECKLIST_EMOCIONAL, 1):
        resp = input(f"\n{i}. {pregunta} ").strip().lower()
        # Las respuestas "malas" que indican riesgo emocional
        if i == 1 and resp == "n":
            advertencias.append("[!] Sueno insuficiente — esperar")
        if i == 2 and resp == "n":
            advertencias.append("[!] Demasiado pronto tras perdida — esperar 48h")
        if i == 3 and resp == "s":
            advertencias.append("[!] Posible FOMO activo — el precio subio mucho hoy")
        if i == 4 and resp == "n":
            advertencias.append("[!] Sensacion de urgencia — senal de sesgo emocional")
        if i == 5 and resp == "n":
            advertencias.append("[!] Sin confirmacion de 2 fuentes — incumple Regla 4")

    if advertencias:
        print("\nADVERTENCIAS:")
        for a in advertencias:
            print(f"  {a}")
        print("\n[X] RECOMENDACION: NO operar ahora. Vuelve cuando se resuelvan las advertencias.")
        return False
    else:
        print("\n[OK] Estado emocional OK — puedes continuar al formulario.")
        return True

def formulario_nuevo_trade():
    print("\n" + "="*50)
    print("  DIARIO PRE-TRADE — Regla de Oro #6")
    print("="*50)
    print("Completa este formulario antes de ejecutar el trade.")
    print("Si no puedes responder en 5 min, no tienes suficiente conviccion.\n")

    # Primero el checklist emocional
    ok_emocional = checklist_emocional()
    if not ok_emocional:
        salir = input("\nContinuar de todas formas? (escribe 'si' para ignorar advertencias): ").strip().lower()
        if salir != "si":
            print("Trade cancelado. Buena decision.")
            return

    print("\n" + "-"*50)
    print("  FORMULARIO DE INVERSION")
    print("-"*50)

    entrada = {"fecha": datetime.datetime.now().isoformat()[:16], "advertencias_emocionales": not ok_emocional}
    for campo, pregunta in PREGUNTAS_TRADE:
        print(f"\n{pregunta}")
        resp = input("-> ").strip()
        entrada[campo] = resp

        # Validaciones en tiempo real
        if campo == "score_checklist":
            try:
                sc = int(resp)
                if sc < 20:
                    print(f"  [!] Score {sc}/30 esta por debajo del minimo (20). Considera no operar.")
                elif sc >= 25:
                    print(f"  [OK] Score {sc}/30 — buena conviccion.")
            except ValueError:
                pass
        if campo == "estado_emocional":
            try:
                stress = int(resp)
                if stress > 7:
                    print(f"  [!] Estres {stress}/10 — por encima del umbral (7). Regla 7: no operar.")
                elif stress <= 3:
                    print(f"  [OK] Estado tranquilo ({stress}/10).")
            except ValueError:
                pass
        if campo == "capital":
            try:
                cap = float(resp.replace("$","").replace(" ",""))
                if cap > 30:
                    print(f"  [i] Trade >$30 — Regla 5: deberias esperar 24h antes de ejecutar.")
            except ValueError:
                pass

    # Resumen final
    print("\n" + "="*50)
    print("  RESUMEN — LEE ESTO ANTES DE CONFIRMAR")
    print("="*50)
    print(f"  Mercado:    {entrada.get('mercado')}")
    print(f"  Direccion:  {entrada.get('direccion')}")
    print(f"  Capital:    ${entrada.get('capital')}")
    print(f"  Tesis:      {entrada.get('tesis')}")
    print(f"  Contra:     {entrada.get('argumento_contra')}")
    print(f"  Score:      {entrada.get('score_checklist')}/30")
    print(f"  Estres:     {entrada.get('estado_emocional')}/10")

    confirmar = input("\nGuardar en diario y proceder? (si/no): ").strip().lower()
    if confirmar == "si":
        diario = cargar_diario()
        diario.append(entrada)
        guardar_diario(diario)
        print(f"\n[OK] Registro guardado en {DIARIO_F}")
        print("Ahora puedes ejecutar el trade en Polymarket.")
    else:
        print("\n[X] Trade no confirmado. Registro descartado.")

def mostrar_historial():
    diario = cargar_diario()
    if not diario:
        print("Sin entradas en el diario de trading.")
        return
    print(f"\n{'='*60}")
    print(f"  HISTORIAL DE TRADES — ultimas {min(10, len(diario))} entradas")
    print(f"{'='*60}")
    for e in diario[-10:][::-1]:
        estado = "[!] EMOC" if e.get("advertencias_emocionales") else "[OK]"
        print(f"\n  [{e['fecha']}] {estado}")
        print(f"  {e.get('direccion','')} {e.get('mercado','')} | ${e.get('capital','')} | Score:{e.get('score_checklist','?')}/30")
        print(f"  Tesis: {e.get('tesis','')[:80]}")

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--nuevo" in args:
        formulario_nuevo_trade()
    elif "--historial" in args:
        mostrar_historial()
    elif "--checklist" in args:
        checklist_emocional()
    else:
        print("Uso: python diario_trading.py [--nuevo | --historial | --checklist]")
        print("  --nuevo      : formulario pre-trade completo")
        print("  --historial  : ver ultimas 10 entradas")
        print("  --checklist  : solo checklist emocional rapido")
