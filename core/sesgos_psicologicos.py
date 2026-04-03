"""
sesgos_psicologicos.py
Guardian mental pre-trade: detecta los 15 sesgos psicologicos mas peligrosos
en mercados de prediccion. Se puede importar o ejecutar como CLI.

Uso como modulo:
    from sesgos_psicologicos import detectar_sesgos, describir_sesgo
    alertas = detectar_sesgos(contexto)

Uso como CLI:
    python sesgos_psicologicos.py
"""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HISTORIAL_FILE = Path(__file__).parent / "historial_trades.json"

# ═══════════════════════════════════════════════════════════════════════════
# DEFINICIONES DE LOS 15 SESGOS
# ═══════════════════════════════════════════════════════════════════════════

SESGOS = {
    1: {
        "codigo":  "FOMO",
        "nombre":  "FOMO — Fear Of Missing Out",
        "nivel":   "ROJO",
        "definicion": (
            "Entras en un mercado porque esta subiendo rapido y tienes miedo "
            "de perderte la ganancia, no porque el analisis lo justifique."
        ),
        "senales": [
            "El precio subio mas de 15pp en las ultimas 24h",
            "Llevas mas de 10 minutos mirando el mismo mercado sin decision",
            "Tu primer pensamiento fue 'esto no puede fallar'",
            "Encontraste el mercado porque alguien lo menciono",
        ],
        "pregunta_control": (
            "Si el precio fuera el mismo que hace 3 dias, habrias entrado igualmente?"
        ),
        "respuesta_peligrosa": "NO",
        "accion": "Si la respuesta es NO, es FOMO. No entres.",
        "antidoto": "Espera 24h. Si al dia siguiente el analisis sigue siendo valido, entonces entra.",
    },
    2: {
        "codigo":  "TACO",
        "nombre":  "TACO Trade — Too Afraid to Cut Out",
        "nivel":   "ROJO",
        "definicion": (
            "Mantener una posicion perdedora porque admitir la perdida "
            "duele mas que la perdida misma. El ego bloquea la razon."
        ),
        "senales": [
            "La posicion lleva mas de 7 dias en perdidas sostenidas",
            "Te has dicho 'ya recuperara' mas de una vez",
            "Has buscado activamente noticias que justifiquen quedarte",
            "La tesis original ha cambiado pero sigues dentro",
        ],
        "pregunta_control": (
            "Si no tuviera esta posicion ahora mismo, la abriria hoy a este precio?"
        ),
        "respuesta_peligrosa": "NO",
        "accion": "Si la respuesta es NO, vende ahora. El tiempo no recupera capital perdido.",
        "antidoto": "Evalua cada posicion como si la estuvieras abriendo hoy. Precio de entrada = irrelevante.",
    },
    3: {
        "codigo":  "CONFIRM",
        "nombre":  "Sesgo de Confirmacion",
        "nivel":   "AMARILLO",
        "definicion": (
            "Solo lees noticias que confirman lo que ya crees. "
            "El cerebro filtra automaticamente la informacion contradictoria."
        ),
        "senales": [
            "Solo has consultado fuentes que apoyan tu posicion",
            "No has buscado activamente el argumento contrario",
            "Descartaste una noticia porque 'ese medio es tendencioso'",
            "El argumento contrario ni siquiera lo conoces",
        ],
        "pregunta_control": "Cual es el mejor argumento en CONTRA de mi posicion?",
        "respuesta_peligrosa": "No lo se",
        "accion": "Protocolo obligatorio: escribe en una frase el mejor argumento contrario. Si no puedes, no entres.",
        "antidoto": "Para cada analisis: busca activamente 'por que podria estar equivocado' antes de 'por que tengo razon'.",
    },
    4: {
        "codigo":  "DISPOS",
        "nombre":  "Efecto Disposicion",
        "nivel":   "AMARILLO",
        "definicion": (
            "Vender ganadores demasiado pronto para 'asegurar' y aguantar "
            "perdedores demasiado tiempo esperando recuperar."
        ),
        "senales": [
            "Tu posicion ganadora lleva +25% y piensas en vender 'para asegurar'",
            "Pero tu posicion perdedora sigue abierta sin plazo de corte",
            "Sientes alivio al cerrar ganancias aunque la tesis no ha cambiado",
            "Sientes resistencia a cerrar perdidas aunque la tesis si ha cambiado",
        ],
        "pregunta_control": "En ambas posiciones (ganadora y perdedora): sigue siendo valida la tesis original?",
        "respuesta_peligrosa": "Tesis perdedora invalida pero sigo dentro",
        "accion": "Cierra la que tiene la tesis invalidada, no la que tiene ganancias.",
        "antidoto": "Evalua si la tesis original sigue vigente. Si no lo esta, cierra independientemente del resultado.",
    },
    5: {
        "codigo":  "GAMBLER",
        "nombre":  "Gambler's Fallacy — Falacia del Jugador",
        "nivel":   "AMARILLO",
        "definicion": (
            "Creer que despues de varios resultados iguales, "
            "el contrario es 'mas probable ahora'. Cada evento es independiente."
        ),
        "senales": [
            "Piensas 'este tipo de mercado ha resuelto YES varias veces, ahora toca NO'",
            "Usas el historial de resoluciones de mercados similares como predictor",
            "Sientes que 'ya era hora' de que cambiara la tendencia",
        ],
        "pregunta_control": "El historico de resoluciones anteriores, cambia la probabilidad de ESTE evento especifico?",
        "respuesta_peligrosa": "SI",
        "accion": "No. Cada mercado es matematicamente independiente. Analiza solo los fundamentos actuales.",
        "antidoto": "Trata cada mercado como si fuera el primero que analizas. El historial no es informacion sobre el futuro.",
    },
    6: {
        "codigo":  "OVERCONF",
        "nombre":  "Exceso de Confianza — Overconfidence Bias",
        "nivel":   "ROJO",
        "definicion": (
            "Sobrestimar tu ventaja informativa o la precision de tu analisis. "
            "Especialmente peligroso tras una racha ganadora."
        ),
        "senales": [
            "Estimas mas del 85% de certeza en un mercado geopolitico",
            "Llevas 3 o mas trades ganadores seguidos",
            "El edge que calculas es mayor de 30pp",
            "Crees que tienes informacion que el mercado no tiene",
        ],
        "pregunta_control": "Que informacion concreta y verificable tengo que el mercado de $5M+ no tiene?",
        "respuesta_peligrosa": "Solo mi intuicion o experiencia",
        "accion": "Si >85% certeza en geopolitica: reduce 15pp. Si 3 ganadores seguidos: reduce tamaño 20%. Si edge >30pp: busca que estas pasando por alto.",
        "antidoto": "Regla de humildad: en mercados geopoliticos, nadie tiene >80% de certeza real. El mercado es agregado de miles de analistas.",
    },
    7: {
        "codigo":  "ANCHOR",
        "nombre":  "Anclaje — Anchoring Bias",
        "nivel":   "AMARILLO",
        "definicion": (
            "Darle demasiado peso al primer numero que ves (precio de entrada, "
            "precio maximo historico) para evaluar el precio actual."
        ),
        "senales": [
            "El precio actual 'te parece caro' solo porque compraste mas barato",
            "Calculas ganancias/perdidas desde tu precio de entrada, no desde el valor real",
            "El precio de entrada funciona como tu referencia mental de 'precio justo'",
            "No cerraras la posicion hasta 'volver al punto de entrada'",
        ],
        "pregunta_control": "Si alguien me pregunta el precio justo de este mercado sin saber mi entrada, que responderia?",
        "respuesta_peligrosa": "Mi precio de entrada seria la referencia",
        "accion": "El mercado no sabe ni le importa donde compraste. Evalua siempre al precio actual de mercado.",
        "antidoto": "Imagina que un amigo te pide analizar este mercado sin decirle que ya tienes posicion. Ese es el analisis correcto.",
    },
    8: {
        "codigo":  "RECENCY",
        "nombre":  "Sesgo de Recencia",
        "nivel":   "AMARILLO",
        "definicion": (
            "Dar demasiado peso a eventos recientes sobre la distribucion "
            "de probabilidades. Un evento de hoy no cambia el largo plazo."
        ),
        "senales": [
            "Un evento de hoy te hace cambiar drasticamente tu estimacion",
            "Usas noticias de las ultimas 24h como base principal del analisis",
            "El 'trend' reciente domina tu razonamiento sobre los fundamentos estructurales",
        ],
        "pregunta_control": "Este evento de hoy, cambia los FUNDAMENTOS estructurales del mercado o solo el ruido?",
        "respuesta_peligrosa": "Cambia todo mi analisis",
        "accion": "Un evento reciente no cambia la distribucion de probabilidad a largo plazo. Verifica con fuentes A/B si es un cambio estructural.",
        "antidoto": "Pregunta: 'Dentro de 30 dias, este evento seguira siendo relevante?' Si no, es ruido.",
    },
    9: {
        "codigo":  "HERD",
        "nombre":  "Efecto Manada — Herding",
        "nivel":   "ROJO",
        "definicion": (
            "Seguir lo que hace la mayoria porque 'todos no pueden estar equivocados'. "
            "En mercados de prediccion, la mayoria SUELE estar equivocada en los extremos."
        ),
        "senales": [
            "Encontraste el mercado en Twitter/X, Telegram o redes sociales",
            "La razon principal para entrar es que 'mucha gente lo esta haciendo'",
            "El volumen de este mercado subio de repente (posible coordinacion)",
            "Alguien con muchos seguidores lo recomendo",
        ],
        "pregunta_control": "Si ninguna otra persona en el mundo hubiera mencionado este mercado, lo habria encontrado y analizado yo solo?",
        "respuesta_peligrosa": "No, lo encontre por recomendacion",
        "accion": "Para. Analisis independiente desde cero. La opinion de otros no es tu edge.",
        "antidoto": "Tu edge viene de analizar mejor, no de seguir a otros. Si otros ya lo saben, el precio ya lo refleja.",
    },
    10: {
        "codigo":  "ILLUSION",
        "nombre":  "Ilusion de Control",
        "nivel":   "AMARILLO",
        "definicion": (
            "Creer que puedes influir en el resultado de un evento probabilistico. "
            "Revisar el precio cada 5 minutos no cambia nada."
        ),
        "senales": [
            "Revisas el precio de tu posicion mas de 5 veces al dia",
            "Crees que 'estar atento' te da ventaja sobre el resultado",
            "Sientes ansiedad cuando no puedes revisar el precio",
            "Preparas respuestas a escenarios que no puedes controlar",
        ],
        "pregunta_control": "Mi revision del precio cambia la probabilidad del evento subyacente?",
        "respuesta_peligrosa": "SI",
        "accion": "Una vez abierta la posicion, el unico control real es: mantener o cerrar. Nada mas.",
        "antidoto": "Pon alertas de precio en vez de revisar manualmente. Dedica ese tiempo al analisis de nuevos mercados.",
    },
    11: {
        "codigo":  "AVAIL",
        "nombre":  "Sesgo de Disponibilidad",
        "nivel":   "AMARILLO",
        "definicion": (
            "Sobrestimar la probabilidad de eventos que recuerdas facilmente, "
            "especialmente si son recientes, vividos o emocionales."
        ),
        "senales": [
            "Sobrestimas la probabilidad de guerra nuclear porque viste noticias de Iran",
            "Infravalorar ceasefire porque los ultimos dias viste noticias de escalada",
            "Tu estimacion cambia segun las ultimas noticias que leiste",
            "Los eventos que recuerdas con detalle te parecen mas probables",
        ],
        "pregunta_control": "Mi estimacion de probabilidad se basa en datos estadisticos o en cuanto recuerdo noticias relacionadas?",
        "respuesta_peligrosa": "En lo que recuerdo",
        "accion": "Busca datos base historicos (base rates). Cuantos conflictos similares terminaron en X tiempo? Esa es la probabilidad base.",
        "antidoto": "Exige un dato de base rate antes de cualquier estimacion. 'En conflictos similares historicamente, la resolucion tarda X tiempo.'",
    },
    12: {
        "codigo":  "MONEY",
        "nombre":  "Money Illusion — Ilusion Monetaria",
        "nivel":   "AMARILLO",
        "definicion": (
            "Pensar en terminos absolutos ($) en lugar de relativos (%). "
            "'Solo son $5' puede ser el 25% del capital en ese mercado."
        ),
        "senales": [
            "Defines el riesgo como 'solo X dolares' sin calcular el porcentaje del capital",
            "Consideras una perdida 'pequeña' por su valor absoluto, no por su impacto relativo",
            "Calculas ganancias en dolares, no en ROI ni en impacto sobre el portfolio",
        ],
        "pregunta_control": "Que porcentaje de mi capital total representa esta posicion? Y esta perdida potencial?",
        "respuesta_peligrosa": "No lo calcule",
        "accion": "Siempre calcular en % del capital total. Una perdida de $5 sobre $50 disponibles es el 10%, no 'solo $5'.",
        "antidoto": "Convierte TODOS los valores a porcentaje del capital antes de cualquier decision.",
    },
    13: {
        "codigo":  "OUTCOME",
        "nombre":  "Sesgo de Resultado — Outcome Bias",
        "nivel":   "AMARILLO",
        "definicion": (
            "Juzgar una decision por su resultado en vez de por la calidad del proceso. "
            "Una mala decision puede dar buen resultado por azar, y viceversa."
        ),
        "senales": [
            "Describes un trade perdedor como 'mala decision' sin analizar si el proceso fue correcto",
            "Describes un trade ganador como 'buena decision' aunque entraste por FOMO",
            "Tu confianza sube despues de ganar aunque no sabes por que ganaste",
            "Usas 'el resultado' para validar tu metodologia",
        ],
        "pregunta_control": "Si este trade hubiera dado el resultado contrario, habria sido una mala decision con el mismo proceso?",
        "respuesta_peligrosa": "Si, el resultado define si fue buena decision",
        "accion": "Evalua el PROCESO, no el resultado. Una buena decision con mala suerte sigue siendo buena decision.",
        "antidoto": "Usa el historial de calibracion (Brier score) para evaluar tu metodologia, no el win rate simple.",
    },
    14: {
        "codigo":  "SNAKEBITE",
        "nombre":  "Efecto Snake Bite",
        "nivel":   "AMARILLO",
        "definicion": (
            "Volverse excesivamente conservador despues de una perdida, "
            "evitando oportunidades reales por miedo irracional a repetir."
        ),
        "senales": [
            "Evitas categorias enteras de mercados despues de una perdida en esa categoria",
            "Reduces el tamaño de todos los trades aunque el analisis no haya cambiado",
            "El miedo a perder domina sobre el analisis del edge",
            "Cada decision incluye el pensamiento 'si me pasa lo mismo que la ultima vez'",
        ],
        "pregunta_control": "El edge de este mercado especifico esta afectado por mi perdida anterior en otro mercado?",
        "respuesta_peligrosa": "SI",
        "accion": "El historial personal de perdidas no cambia la probabilidad del proximo mercado. Analiza cada uno independientemente.",
        "antidoto": "Vuelve al proceso. Evalua el edge con el protocolo estandar. Si el edge es real, la perdida anterior es irrelevante.",
    },
    15: {
        "codigo":  "SUNK",
        "nombre":  "Sunk Cost Fallacy — Costo Hundido",
        "nivel":   "ROJO",
        "definicion": (
            "Mantener una posicion porque 'ya invertiste mucho en ella' "
            "(tiempo, dinero, esfuerzo). El pasado no es razon para el futuro."
        ),
        "senales": [
            "Continuas con una posicion porque 'llevo semanas analizando esto'",
            "El argumento principal para no cerrar es 'ya perdi tanto que lo mismo aguanto'",
            "Sientes que cerrar seria 'desperdiciar' el trabajo ya hecho",
            "El tiempo invertido en analisis aparece como justificacion para mantener",
        ],
        "pregunta_control": "Si tuviera que analizar este mercado desde cero hoy, sin el trabajo previo, llegaria a la misma conclusion?",
        "respuesta_peligrosa": "NO",
        "accion": "El tiempo ya invertido no recupera capital. La decision correcta de hoy no depende del trabajo de ayer.",
        "antidoto": "El sunk cost es cognitivamente el pasado. La decision es siempre sobre el futuro. Separa mentalmente ambos.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# DETECTOR AUTOMATICO DE SESGOS
# ═══════════════════════════════════════════════════════════════════════════

def detectar_sesgos(contexto: dict) -> list:
    """
    Detecta sesgos activos dado un contexto de mercado/posicion.

    Parametros del contexto:
        precio_cambio_24h_pp  : cambio de precio en 24h en puntos porcentuales (float)
        precio_cambio_7d_pp   : cambio en 7 dias (float)
        encontrado_por_red    : True si el mercado lo encontraste por redes/recomendacion
        minutos_mirando       : minutos observando el mercado (int)
        primer_pensamiento_ok : False si primer pensamiento fue 'no puede fallar'
        dias_en_perdidas      : dias consecutivos en perdidas (int, 0 si ganando)
        tesis_cambiada        : True si la tesis original ya no es valida
        ganadores_seguidos    : numero de trades ganadores consecutivos recientes (int)
        edge_calculado_pp     : edge calculado en pp (float)
        certeza_estimada_pct  : porcentaje de certeza estimado (float, 0-100)
        ganadora_pct          : p/l de posicion ganadora en % (float)
        perdedora_abierta     : True si hay posicion perdedora abierta
        revisiones_dia        : numero de veces que revisaste el precio hoy (int)
        fuentes_contrarias    : True si buscaste activamente fuentes contrarias
        perdida_reciente      : True si tuviste una perdida importante recientemente
        posicion_pct_capital  : porcentaje del capital en esta posicion (float)
        trades_ganados_total  : numero de trades ganados total (int)
        trades_total          : numero de trades totales (int)

    Retorna lista de dicts: [{"id": N, "codigo": "FOMO", "nombre": ...,
                               "nivel": "ROJO", "senales_activas": [...],
                               "pregunta_control": ..., "accion": ...}]
    """
    alertas = []

    def alerta(id_sesgo, senales):
        s = SESGOS[id_sesgo]
        alertas.append({
            "id":               id_sesgo,
            "codigo":           s["codigo"],
            "nombre":           s["nombre"],
            "nivel":            s["nivel"],
            "senales_activas":  senales,
            "pregunta_control": s["pregunta_control"],
            "accion":           s["accion"],
            "antidoto":         s["antidoto"],
        })

    # 1. FOMO
    senales_fomo = []
    if contexto.get("precio_cambio_24h_pp", 0) > 15:
        senales_fomo.append(f"Precio subio {contexto['precio_cambio_24h_pp']:.1f}pp en 24h (umbral: 15pp)")
    if contexto.get("minutos_mirando", 0) > 10:
        senales_fomo.append(f"Llevas {contexto['minutos_mirando']} min mirando el mercado (umbral: 10)")
    if not contexto.get("primer_pensamiento_ok", True):
        senales_fomo.append("Primer pensamiento fue 'esto no puede fallar'")
    if contexto.get("encontrado_por_red", False):
        senales_fomo.append("Encontraste el mercado por recomendacion de terceros")
    if senales_fomo:
        alerta(1, senales_fomo)

    # 2. TACO TRADE
    senales_taco = []
    if contexto.get("dias_en_perdidas", 0) > 7:
        senales_taco.append(f"Posicion en perdidas {contexto['dias_en_perdidas']} dias consecutivos (umbral: 7)")
    if contexto.get("tesis_cambiada", False):
        senales_taco.append("La tesis original ya no es valida pero la posicion sigue abierta")
    if senales_taco:
        alerta(2, senales_taco)

    # 3. SESGO DE CONFIRMACION
    if not contexto.get("fuentes_contrarias", True):
        alerta(3, ["No has buscado activamente fuentes o argumentos contrarios a tu posicion"])

    # 4. EFECTO DISPOSICION
    senales_disp = []
    if contexto.get("ganadora_pct", 0) > 25 and contexto.get("perdedora_abierta", False):
        senales_disp.append(
            f"Posicion ganadora al +{contexto['ganadora_pct']:.0f}% pensando en vender, pero perdedora sigue abierta"
        )
    if senales_disp:
        alerta(4, senales_disp)

    # 6. EXCESO DE CONFIANZA
    senales_oc = []
    if contexto.get("certeza_estimada_pct", 0) > 85:
        senales_oc.append(f"Certeza estimada {contexto['certeza_estimada_pct']:.0f}% en mercado geopolitico (umbral: 85%)")
    if contexto.get("ganadores_seguidos", 0) >= 3:
        senales_oc.append(f"{contexto['ganadores_seguidos']} trades ganadores seguidos — riesgo de sobrestimar habilidad")
    if contexto.get("edge_calculado_pp", 0) > 30:
        senales_oc.append(f"Edge calculado {contexto['edge_calculado_pp']:.0f}pp — busca activamente que estas pasando por alto")
    if senales_oc:
        alerta(6, senales_oc)

    # 7. ANCLAJE — siempre presente con posiciones abiertas
    if contexto.get("tiene_posicion_abierta", False) and contexto.get("precio_entrada") is not None:
        precio_e  = contexto["precio_entrada"]
        precio_a  = contexto.get("precio_actual", precio_e)
        diferencia = abs(precio_a - precio_e) * 100
        if diferencia > 5:
            alerta(7, [
                f"Precio de entrada {precio_e:.3f} vs actual {precio_a:.3f} — diferencia {diferencia:.1f}pp",
                "Riesgo de usar el precio de entrada como referencia mental del 'precio justo'"
            ])

    # 8. SESGO DE RECENCIA
    if abs(contexto.get("precio_cambio_24h_pp", 0)) > 10:
        alerta(8, [
            f"Movimiento de {contexto['precio_cambio_24h_pp']:+.1f}pp en 24h puede distorsionar la perspectiva",
            "Verifica si este movimiento cambia los fundamentos estructurales o es ruido"
        ])

    # 9. EFECTO MANADA
    if contexto.get("encontrado_por_red", False):
        alerta(9, ["Encontraste el mercado por recomendacion externa — analisis independiente obligatorio"])

    # 10. ILUSION DE CONTROL
    if contexto.get("revisiones_dia", 0) > 5:
        alerta(10, [
            f"Revisaste el precio {contexto['revisiones_dia']} veces hoy (umbral: 5)",
            "Revisar el precio no cambia la probabilidad del evento subyacente"
        ])

    # 11. SESGO DE DISPONIBILIDAD — detectar en mercados con noticias intensas
    if contexto.get("noticias_intensas", False):
        alerta(11, [
            "Contexto de noticias intensas — riesgo de sobrestimar probabilidades por cobertura mediatica",
            "Busca base rates historicos antes de estimar probabilidad"
        ])

    # 12. MONEY ILLUSION
    if contexto.get("posicion_pct_capital", 0) > 15 and not contexto.get("calculo_porcentual_hecho", True):
        alerta(12, [
            f"Posicion representa {contexto['posicion_pct_capital']:.1f}% del capital — asegurate de pensar en % no en $",
        ])

    # 14. SNAKE BITE
    if contexto.get("perdida_reciente", False):
        alerta(14, [
            "Perdida reciente detectada — riesgo de aplicar filtros irracionales a este analisis",
            "El historial de perdidas no cambia la probabilidad de este mercado especifico"
        ])

    # 15. SUNK COST
    if contexto.get("horas_analisis", 0) > 3 and not contexto.get("tesis_solida", True):
        alerta(15, [
            f"Llevas {contexto['horas_analisis']} horas en este analisis — riesgo de sunk cost si la tesis es debil",
            "El tiempo invertido en analisis no es razon para entrar en un trade suboptimo"
        ])

    # Ordenar: ROJO primero, luego AMARILLO
    orden = {"ROJO": 0, "AMARILLO": 1, "VERDE": 2}
    alertas.sort(key=lambda x: orden.get(x["nivel"], 2))
    return alertas


def detectar_sesgos_posicion(posicion: dict, historial: dict = None) -> list:
    """
    Version conveniente: detecta sesgos a partir de una posicion del portfolio.json
    """
    if historial is None:
        try:
            with open(HISTORIAL_FILE, encoding="utf-8") as f:
                historial = json.load(f)
        except Exception:
            historial = {"trades": [], "estadisticas": {}}

    stats   = historial.get("estadisticas", {})
    trades  = historial.get("trades", [])

    # Calcular ganadores seguidos recientes
    resueltos = [t for t in trades if t["estado"] == "resuelto"]
    ganadores_seguidos = 0
    for t in reversed(resueltos):
        if t["resultado"] == "ganado":
            ganadores_seguidos += 1
        else:
            break

    # Calcular P/L de la posicion
    precio_e = posicion.get("precio_entrada_avg", 0.5)
    precio_a = posicion.get("precio_actual", precio_e)
    pnl_pct  = posicion.get("pnl_pct", 0) or 0

    contexto = {
        "precio_cambio_24h_pp":    0,        # sin datos live
        "precio_cambio_7d_pp":     0,
        "encontrado_por_red":      False,
        "minutos_mirando":         0,
        "primer_pensamiento_ok":   True,
        "dias_en_perdidas":        0 if pnl_pct >= 0 else 8,
        "tesis_cambiada":          False,
        "ganadores_seguidos":      ganadores_seguidos,
        "edge_calculado_pp":       posicion.get("edge_estimado_pp", 0) or 0,
        "certeza_estimada_pct":    (posicion.get("prob_propia_estimada") or 0.5) * 100,
        "ganadora_pct":            max(0, pnl_pct),
        "perdedora_abierta":       False,
        "revisiones_dia":          0,
        "fuentes_contrarias":      bool(posicion.get("fuentes_usadas")),
        "perdida_reciente":        False,
        "posicion_pct_capital":    (posicion.get("capital_invertido", 0) / 434.24) * 100,
        "calculo_porcentual_hecho":True,
        "tiene_posicion_abierta":  True,
        "precio_entrada":          precio_e,
        "precio_actual":           precio_a,
        "noticias_intensas":       True,   # Iran — contexto de noticias intensas conocido
        "tesis_solida":            True,
        "horas_analisis":          0,
    }

    # Detectar ANCLAJE si hay diferencia significativa
    # Detectar RECENCY por contexto Iran activo
    # Agregar CONFIRMACION si no tiene fuentes
    return detectar_sesgos(contexto)


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT FORMATEADO
# ═══════════════════════════════════════════════════════════════════════════

def sep(char="─", ancho=66):
    print(char * ancho)

def mostrar_sesgo(a, compacto=False):
    iconos = {"ROJO": "[X]", "AMARILLO": "[~]", "VERDE": "[V]"}
    icono  = iconos.get(a["nivel"], "[?]")
    print(f"\n  {icono} #{a['id']:02d} — {a['nombre']}  [{a['nivel']}]")
    if not compacto:
        for s in a["senales_activas"]:
            print(f"       * {s}")
        print(f"       ? {a['pregunta_control']}")
        print(f"       > {a['accion']}")
        sep()

def mostrar_todos_los_sesgos():
    """Muestra la ficha completa de los 15 sesgos para consulta."""
    print("=" * 66)
    print("  GUIA COMPLETA — 15 SESGOS PSICOLOGICOS")
    print("=" * 66)
    for id_s, s in SESGOS.items():
        iconos = {"ROJO": "[X]", "AMARILLO": "[~]"}
        icono  = iconos.get(s["nivel"], "[?]")
        print(f"\n  {icono} #{id_s:02d} — {s['nombre']}")
        sep()
        print(f"  Definicion: {s['definicion'][:90]}")
        print(f"  Senales:    {s['senales'][0][:70]}")
        print(f"  Control:    {s['pregunta_control'][:70]}")
        print(f"  Accion:     {s['accion'][:70]}")
        print(f"  Antidoto:   {s['antidoto'][:70]}")
    print()


def mostrar_sesgos_activos(alertas: list, contexto_nombre: str = ""):
    """Muestra los sesgos detectados de forma clara."""
    print("=" * 66)
    titulo = f"  SESGOS DETECTADOS" + (f" — {contexto_nombre}" if contexto_nombre else "")
    print(titulo)
    print("=" * 66)

    if not alertas:
        print("\n  Sin sesgos detectados con los datos disponibles.")
        print("  Contexto insuficiente para deteccion completa — responde el checklist interactivo.")
        return

    rojos    = [a for a in alertas if a["nivel"] == "ROJO"]
    amarillos = [a for a in alertas if a["nivel"] == "AMARILLO"]

    if rojos:
        print(f"\n  [X] SESGOS CRITICOS ({len(rojos)}) — NO OPERAR HASTA RESOLVER:\n")
        for a in rojos:
            mostrar_sesgo(a)

    if amarillos:
        print(f"\n  [~] SESGOS DE ATENCION ({len(amarillos)}) — Analizar antes de proceder:\n")
        for a in amarillos:
            mostrar_sesgo(a, compacto=True)

    print(f"\n  Total sesgos activos: {len(alertas)} ({len(rojos)} criticos, {len(amarillos)} atencion)")


# ═══════════════════════════════════════════════════════════════════════════
# RECORDATORIO DIARIO ROTATIVO
# ═══════════════════════════════════════════════════════════════════════════

def recordatorio_del_dia() -> dict:
    """Selecciona el sesgo del dia de forma rotatoria basandose en la fecha."""
    dia_del_anio = datetime.now().timetuple().tm_yday
    id_sesgo     = (dia_del_anio % 15) + 1
    s            = SESGOS[id_sesgo]
    return {
        "id":       id_sesgo,
        "codigo":   s["codigo"],
        "nombre":   s["nombre"],
        "mensaje":  s["definicion"],
        "antidoto": s["antidoto"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI INTERACTIVO
# ═══════════════════════════════════════════════════════════════════════════

def cli_interactivo():
    """Modo interactivo: hace preguntas y detecta sesgos en tiempo real."""
    print("=" * 66)
    print("  DETECTOR INTERACTIVO DE SESGOS PSICOLOGICOS")
    print("  Responde con s/n a cada pregunta")
    print("=" * 66)

    def preguntar(texto, default=False):
        r = input(f"\n  ? {texto} (s/n): ").strip().lower()
        return r in ("s", "si", "sí", "y", "yes")

    def preguntar_num(texto, default=0):
        try:
            return float(input(f"\n  # {texto}: ").strip() or default)
        except Exception:
            return default

    print("\n  -- CONTEXTO DEL MERCADO --")
    cambio_24h  = preguntar_num("Cambio de precio en las ultimas 24h (pp, ej: 12.5)", 0)
    por_red     = preguntar("Encontraste este mercado por recomendacion de alguien o redes sociales?")
    minutos     = preguntar_num("Cuantos minutos llevas mirando este mercado?", 0)
    primer_ok   = not preguntar("Tu primer pensamiento fue 'esto no puede fallar' o similar?")
    dias_perd   = preguntar_num("Cuantos dias consecutivos lleva esta posicion en perdidas? (0 si gana o es nueva)", 0)
    tesis_ok    = not preguntar("Ha cambiado la tesis original que te hizo entrar?")
    gan_seguidos = preguntar_num("Cuantos trades ganadores seguidos llevas recientemente?", 0)
    edge_pp     = preguntar_num("Cual es el edge calculado en pp? (0 si no lo has calculado)", 0)
    certeza     = preguntar_num("En que % estas seguro de tu estimacion? (ej: 75)", 50)
    revisiones  = preguntar_num("Cuantas veces revisaste el precio de tus posiciones hoy?", 0)
    fuentes_c   = preguntar("Has buscado activamente fuentes o argumentos contrarios a tu tesis?")
    perdida_rec = preguntar("Tuviste una perdida importante en los ultimos 7 dias?")
    pos_pct     = preguntar_num("Que % del capital total representa esta posicion? (ej: 20)", 0)

    contexto = {
        "precio_cambio_24h_pp":    cambio_24h,
        "encontrado_por_red":      por_red,
        "minutos_mirando":         int(minutos),
        "primer_pensamiento_ok":   primer_ok,
        "dias_en_perdidas":        int(dias_perd),
        "tesis_cambiada":          not tesis_ok,
        "ganadores_seguidos":      int(gan_seguidos),
        "edge_calculado_pp":       edge_pp,
        "certeza_estimada_pct":    certeza,
        "revisiones_dia":          int(revisiones),
        "fuentes_contrarias":      fuentes_c,
        "perdida_reciente":        perdida_rec,
        "posicion_pct_capital":    pos_pct,
        "calculo_porcentual_hecho":True,
        "noticias_intensas":       abs(cambio_24h) > 5,
        "tiene_posicion_abierta":  True,
        "ganadora_pct":            0,
        "perdedora_abierta":       False,
        "tesis_solida":            tesis_ok,
        "horas_analisis":          0,
    }

    alertas = detectar_sesgos(contexto)
    mostrar_sesgos_activos(alertas, "Analisis interactivo")

    # Recordatorio del dia
    r = recordatorio_del_dia()
    print(f"\n  SESGO DEL DIA (#{r['id']} — {r['nombre']}):")
    print(f"  {r['mensaje'][:100]}")
    print(f"  Antidoto: {r['antidoto'][:100]}")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--guia":
        mostrar_todos_los_sesgos()
    else:
        cli_interactivo()
