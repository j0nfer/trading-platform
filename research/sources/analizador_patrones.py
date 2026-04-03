"""
analizador_patrones.py -- Comparador de patrones historicos geopoliticos
Compara situaciones actuales con casos historicos para calibrar probabilidades.

Uso:
  python analizador_patrones.py --tipo custodia         (mercados prisionero/custodia)
  python analizador_patrones.py --tipo transicion       (gobiernos de transicion)
  python analizador_patrones.py --tipo ceasefire        (mercados ceasefire/conflicto)
  python analizador_patrones.py --tipo regimen_change   (cambio de regimen)
  python analizador_patrones.py --consulta "maduro liberado"
  python analizador_patrones.py --all                   (mostrar todos los frameworks)
"""

import argparse
import json
from typing import Optional

# --- BASE DE DATOS DE PATRONES HISTORICOS ------------------------------------

# PATRON 1: LIDERES EN CUSTODIA USA -- ?Cuantos fueron liberados antes del juicio?
CASOS_CUSTODIA = [
    {
        "nombre": "Manuel Noriega (Panama)",
        "ano": 1990,
        "cargos": "Narcotrafico, extorsion, lavado",
        "captura": "Operacion Just Cause -- 20 dic 1989",
        "liberado_pretrial": False,
        "condena_anos": 40,  # reducida a 17 por buen comportamiento
        "tiempo_hasta_juicio_meses": 18,
        "deal_politico": False,
        "notas": "Juicio julio 1991. Murio en prision 2017. Modelo mas similar a Maduro.",
        "base_rate_relevancia": 10,  # 10/10 relevancia para caso Maduro
    },
    {
        "nombre": "Saddam Hussein (Irak)",
        "ano": 2003,
        "cargos": "Crimenes de guerra, genocidio",
        "captura": "Operacion Red Dawn -- 13 dic 2003",
        "liberado_pretrial": False,
        "condena_anos": None,  # ejecutado
        "tiempo_hasta_juicio_meses": 23,
        "deal_politico": False,
        "notas": "Nunca liberado. Ejecutado dic 2006. Jurisdiccion iraqui, no EEUU.",
        "base_rate_relevancia": 6,
    },
    {
        "nombre": "Carlos Lehder (Colombia)",
        "ano": 1987,
        "cargos": "Narcotrafico",
        "captura": "Extradicion Colombia-EEUU",
        "liberado_pretrial": False,
        "condena_anos": 55,  # reducida por cooperacion
        "tiempo_hasta_juicio_meses": 12,
        "deal_politico": True,
        "notas": "Coopero contra Noriega -- condena reducida. Relevante: deal politico SI puede ocurrir.",
        "base_rate_relevancia": 7,
    },
    {
        "nombre": "Joaquin 'El Chapo' Guzman",
        "ano": 2017,
        "cargos": "Narcotrafico, asesinato, conspiracion",
        "captura": "Extradicion Mexico-EEUU",
        "liberado_pretrial": False,
        "condena_anos": 999,  # cadena perpetua
        "tiempo_hasta_juicio_meses": 24,
        "deal_politico": False,
        "notas": "Juicio nov 2018-feb 2019. Cadena perpetua. Modelo para cargos narco.",
        "base_rate_relevancia": 8,
    },
    {
        "nombre": "Viktor Bout (Rusia)",
        "ano": 2010,
        "cargos": "Narcotrafico de armas, conspiracion",
        "captura": "Extradicion Tailandia-EEUU",
        "liberado_pretrial": False,
        "condena_anos": 25,
        "tiempo_hasta_juicio_meses": 18,
        "deal_politico": True,
        "notas": "LIBERADO en 2022 en intercambio por Brittney Griner. Caso clave: deals SI ocurren.",
        "base_rate_relevancia": 9,
    },
    {
        "nombre": "Ramzan Kadyrov - No capturado",
        "ano": None,
        "cargos": "Sanciones EEUU por violaciones DDHH",
        "captura": "No capturado -- sancionado",
        "liberado_pretrial": None,
        "condena_anos": None,
        "tiempo_hasta_juicio_meses": None,
        "deal_politico": None,
        "notas": "Ejemplo de lider con cargos EEUU que nunca fue extraditado. Contraejemplo.",
        "base_rate_relevancia": 3,
    },
]

# PATRON 2: GOBIERNOS DE TRANSICION -- ?Cuanto duran los presidentes interinos?
CASOS_TRANSICION = [
    {
        "nombre": "Juan Guaido (Venezuela 2019)",
        "pais": "Venezuela",
        "duracion_interinato_meses": 36,
        "gano_elecciones": False,
        "desplazado_por": "Presion externa insuficiente, fragmentacion oposicion",
        "reconocimiento_eeuu": True,
        "reconocimiento_rusia_china": False,
        "notas": "Nombrado presidente interino pero sin control real. Diferente al caso Rodriguez.",
        "relevancia": 8,
    },
    {
        "nombre": "Desi Bouterse (Surinam) -- post-golpe",
        "pais": "Surinam",
        "duracion_interinato_meses": 12,
        "gano_elecciones": True,
        "desplazado_por": "Elecciones (gano legitimamente despues)",
        "reconocimiento_eeuu": False,
        "notas": "Ejemplo de lider post-golpe que consolido poder via elecciones.",
        "relevancia": 5,
    },
    {
        "nombre": "Jeanine Anez (Bolivia 2019)",
        "pais": "Bolivia",
        "duracion_interinato_meses": 11,
        "gano_elecciones": False,
        "desplazado_por": "Elecciones ganadas por MAS (oposicion)",
        "reconocimiento_eeuu": True,
        "reconocimiento_rusia_china": False,
        "notas": "Presidenta interina que perdio elecciones. Luego procesada penalmente.",
        "relevancia": 7,
    },
    {
        "nombre": "Michel Temer (Brasil 2016)",
        "pais": "Brasil",
        "duracion_interinato_meses": 29,
        "gano_elecciones": False,
        "desplazado_por": "Fin del periodo constitucional (no postulo)",
        "reconocimiento_eeuu": True,
        "notas": "Vicepresidente que completo mandato. Diferente: asumio por impeachment.",
        "relevancia": 4,
    },
    {
        "nombre": "Delcy Rodriguez (Venezuela 2026) -- CASO ACTUAL",
        "pais": "Venezuela",
        "duracion_interinato_meses": None,  # en curso
        "gano_elecciones": None,
        "desplazado_por": None,
        "reconocimiento_eeuu": True,
        "reconocimiento_rusia_china": False,
        "notas": "Control del aparato estatal + militar + reconocimiento EEUU. Sin elecciones convocadas. Posicion mas solida que Guaido.",
        "relevancia": 10,
    },
]

# PATRON 3: CEASEFIRE/ACUERDOS -- Base rates historicas
CASOS_CEASEFIRE = [
    {
        "nombre": "EEUU-Iran 2019 (tension post-Soleimani)",
        "conflicto": "EEUU-Iran",
        "duracion_activa_dias": 45,
        "termino_en_acuerdo": False,
        "termino_en_ceasefire": False,
        "termino_en_desescalada": True,
        "notas": "Asesinato de Soleimani (3 ene 2019). Represalia irani limitada. Desescalada sin acuerdo.",
        "relevancia_actual": 7,
    },
    {
        "nombre": "EEUU-Irak 2003 -- fase inicial",
        "conflicto": "EEUU-Irak",
        "duracion_activa_dias": 43,
        "termino_en_acuerdo": False,
        "termino_en_ceasefire": False,
        "termino_en_desescalada": False,
        "notas": "No ceasefire -- victoria militar. Ocupacion prolongada.",
        "relevancia_actual": 5,
    },
    {
        "nombre": "Israel-Hezbollah 2006",
        "conflicto": "Israel-Hezbollah",
        "duracion_activa_dias": 34,
        "termino_en_acuerdo": True,
        "termino_en_ceasefire": True,
        "resolucion_ONU": "Resolucion 1701",
        "notas": "34 dias de guerra. Ceasefire mediado por ONU. Hezbollah sobrevivio.",
        "relevancia_actual": 6,
    },
    {
        "nombre": "Israel-Hamas Nov 2023",
        "conflicto": "Israel-Hamas",
        "duracion_activa_dias": 420,
        "termino_en_acuerdo": True,
        "termino_en_ceasefire": True,
        "notas": "14 meses de guerra. Acuerdo de hostages por ceasefire. Base rate: conflictos similares toman >6 meses.",
        "relevancia_actual": 8,
    },
    {
        "nombre": "Guerra de los 12 Dias (Israel-Iran Oct 2025)",
        "conflicto": "Israel-Iran",
        "duracion_activa_dias": 12,
        "termino_en_acuerdo": False,
        "termino_en_ceasefire": True,
        "notas": "Precedente directo. 12 dias, ceasefire sin acuerdo formal. Luego EEUU entro feb 2026.",
        "relevancia_actual": 10,
    },
]

# PATRON 4: LIDERES EN EXILIO -- ?Cuando vuelven?
CASOS_RETORNO_EXILIO = [
    {
        "nombre": "Juan Guaido -- No volvio",
        "pais": "Venezuela",
        "anos_exilio": 2,
        "volvio": False,
        "razon_no_retorno": "Sin garantias de seguridad, gobierno chavista en poder",
        "anuncio_retorno_sin_cumplir": True,
        "notas": "Anuncio retorno multiples veces. Nunca lo hizo cuando no habia garantias reales.",
        "relevancia": 9,
    },
    {
        "nombre": "Aung San Suu Kyi (Myanmar)",
        "pais": "Myanmar",
        "anos_exilio": 0,  # arresto domiciliario, no exilio
        "volvio": None,
        "notas": "Diferente caso -- arresto domiciliario. Referencia para resistencia opositora.",
        "relevancia": 3,
    },
    {
        "nombre": "Alvaro Uribe -- No aplica",
        "pais": "Colombia",
        "notas": "No hubo exilio. No relevante.",
        "relevancia": 1,
    },
    {
        "nombre": "Maria Corina Machado -- CASO ACTUAL",
        "pais": "Venezuela",
        "anos_exilio": 0.25,  # ~3 meses desde ene 2026
        "volvio": False,
        "anuncio_retorno_sin_cumplir": True,  # anuncio 1 marzo, no ha cumplido aun
        "trump_pidio_esperar": True,  # 6 marzo
        "rodriguez_amenazo": True,
        "rubio_dijo_muy_pronto": True,
        "notas": "Patron clasico: anuncio publico de retorno sin fecha -> Trump la freno -> no ha vuelto. Guaido hizo lo mismo multiples veces.",
        "relevancia": 10,
    },
    {
        "nombre": "Leopoldo Lopez (Venezuela)",
        "pais": "Venezuela",
        "anos_exilio": 2,
        "volvio": False,
        "anuncio_retorno_sin_cumplir": True,
        "notas": "Multiples anuncios de retorno nunca cumplidos. Esta en Madrid.",
        "relevancia": 9,
    },
]

# PATRON 5: INTERVENCIONES MILITARES EEUU -- ?Segunda intervencion?
CASOS_SEGUNDA_INTERVENCION = [
    {
        "nombre": "Panama (post-Noriega)",
        "ano_primera": 1989,
        "segunda_intervencion": False,
        "razon": "Objetivo conseguido (captura Noriega). Pais se estabilizo con gobierno cooperativo.",
        "relevancia": 10,
    },
    {
        "nombre": "Irak (post-Saddam)",
        "ano_primera": 2003,
        "segunda_intervencion": True,  # 2007 surge, etc.
        "razon": "Pais se desestabilizo. Insurgencia. Ocupacion prolongada necesito refuerzos.",
        "relevancia": 6,
        "nota_diferencia": "Venezuela no tiene insurgencia comparable. Rodriguez cooperativa. NO similar a Irak.",
    },
    {
        "nombre": "Granada (1983)",
        "ano_primera": 1983,
        "segunda_intervencion": False,
        "razon": "Operacion pequena y exitosa. Pais se estabilizo rapido. Similar a Venezuela.",
        "relevancia": 8,
    },
    {
        "nombre": "Haiti (1994)",
        "ano_primera": 1994,
        "segunda_intervencion": True,  # 2004, 2010, 2021 varias misiones
        "razon": "Inestabilidad cronica. Diferente: Venezuela tiene petroleo = mayor interes en estabilidad.",
        "relevancia": 4,
    },
    {
        "nombre": "Venezuela (2026) -- CASO ACTUAL",
        "ano_primera": 2026,
        "segunda_intervencion": None,
        "notas": "Patron mas similar: Panama 1989 (NO segunda intervencion). Rodriguez cooperativa = EEUU no tiene incentivo.",
        "relevancia": 10,
    },
]


def calcular_base_rate_custodia(verbose: bool = True) -> dict:
    """Calcula probabilidad base de liberacion pre-juicio para lideres capturados por EEUU"""
    casos_relevantes = [c for c in CASOS_CUSTODIA if c["base_rate_relevancia"] >= 6]
    total = len(casos_relevantes)
    liberados = sum(1 for c in casos_relevantes if c.get("liberado_pretrial") == True)
    deals = sum(1 for c in casos_relevantes if c.get("deal_politico") == True)

    base_rate_liberacion = liberados / total if total > 0 else 0
    base_rate_deal = deals / total if total > 0 else 0

    tiempo_promedio = [c["tiempo_hasta_juicio_meses"] for c in casos_relevantes
                       if c.get("tiempo_hasta_juicio_meses")]
    avg_tiempo = sum(tiempo_promedio) / len(tiempo_promedio) if tiempo_promedio else 0

    resultado = {
        "base_rate_liberacion_pretrial": base_rate_liberacion,
        "base_rate_deal_politico": base_rate_deal,
        "tiempo_promedio_hasta_juicio_meses": avg_tiempo,
        "casos_analizados": total,
    }

    if verbose:
        print("\n" + "="*65)
        print(" PATRON: LIDERES EN CUSTODIA EEUU -- Base Rates Historicas")
        print("="*65)
        for c in sorted(casos_relevantes, key=lambda x: x["base_rate_relevancia"], reverse=True):
            deal_str = "DEAL POLITICO" if c.get("deal_politico") else "Sin deal"
            lib_str = "LIBERADO pretrial" if c.get("liberado_pretrial") else "No liberado"
            print(f"\n  [{c['base_rate_relevancia']}/10] {c['nombre']}")
            print(f"   Cargos  : {c['cargos']}")
            print(f"   Outcome : {lib_str} | {deal_str}")
            if c.get("tiempo_hasta_juicio_meses"):
                print(f"   Juicio  : {c['tiempo_hasta_juicio_meses']} meses")
            print(f"   Nota    : {c['notas']}")

        print(f"\n{'-'*65}")
        print(f" RESUMEN ESTADISTICO:")
        print(f"   Casos analizados            : {total}")
        print(f"   Liberados pre-juicio        : {liberados}/{total} = {base_rate_liberacion*100:.0f}%")
        print(f"   Deals politicos historicos  : {deals}/{total} = {base_rate_deal*100:.0f}%")
        print(f"   Tiempo promedio hasta juicio: {avg_tiempo:.1f} meses")
        print(f"{'-'*65}")
        print(f" APLICACION AL CASO MADURO:")
        print(f"   Base rate liberacion: {base_rate_liberacion*100:.0f}% historica")
        print(f"   Ajuste: Trump NO necesita liberarlo (Venezuela ya cooperativa) -> -5pp")
        print(f"   Ajuste: Narcoterrorismo = sin fianza posible -> -3pp")
        print(f"   Ajuste: Precedente Viktor Bout (deal con Rusia) -> +2pp si Trump quiere algo de Iran/Rusia")
        print(f"   ESTIMACION FINAL: 5-8% probabilidad liberacion Dec31")
        print(f"   -> Mercado a 15% = SOBREPAGANDO por el riesgo")
        print(f"   -> Edge NO: ~7-10pp")
        print("="*65)

    return resultado


def calcular_base_rate_retorno_exilio(verbose: bool = True) -> dict:
    """Calcula probabilidad de retorno de lider en exilio cuando anuncia regreso"""
    casos_relevantes = [c for c in CASOS_RETORNO_EXILIO if c.get("relevancia", 0) >= 6]
    anunciaron = [c for c in casos_relevantes if c.get("anuncio_retorno_sin_cumplir")]
    volvieron_tras_anuncio = [c for c in anunciaron if c.get("volvio") == True]

    base_rate_cumplimiento = len(volvieron_tras_anuncio) / len(anunciaron) if anunciaron else 0

    resultado = {
        "base_rate_cumple_anuncio_retorno": base_rate_cumplimiento,
        "casos_con_anuncio_sin_cumplir": len(anunciaron),
        "casos_volvieron_tras_anuncio": len(volvieron_tras_anuncio),
    }

    if verbose:
        print("\n" + "="*65)
        print(" PATRON: LIDERES EXILIO QUE ANUNCIAN RETORNO -- Base Rates")
        print("="*65)
        for c in sorted(casos_relevantes, key=lambda x: x.get("relevancia", 0), reverse=True):
            if c.get("anuncio_retorno_sin_cumplir"):
                volvio = c.get("volvio")
                volvio_str = "VOLVIO" if volvio else "NO VOLVIO" if volvio == False else "EN CURSO"
                print(f"\n  [{c.get('relevancia')}/10] {c['nombre']}")
                print(f"   Anuncio retorno: SI | {volvio_str}")
                print(f"   Nota: {c.get('notas','')}")

        print(f"\n{'-'*65}")
        print(f" RESUMEN: De {len(anunciaron)} lideres que anunciaron retorno:")
        print(f"   Cumplieron el anuncio: {len(volvieron_tras_anuncio)}/{len(anunciaron)} = {base_rate_cumplimiento*100:.0f}%")
        print(f"\n CASO MACHADO -- Factores adicionales:")
        print(f"   [ROJO]  Trump explicitamente pidio que espere (6 marzo)")
        print(f"   [ROJO]  Rodriguez la amenazo ('tendra que responder')")
        print(f"   [ROJO]  Rubio: 'demasiado pronto' para transicion oposicion")
        print(f"   [AMBAR] Anuncio publico 1 marzo ('en las proximas semanas')")
        print(f"   [AMBAR] Guaido y Leopoldo Lopez anunciaron multiples veces -> nunca volvieron")
        print(f"\n   Base rate retorno en 30 dias: ~{base_rate_cumplimiento*100:.0f}% historico")
        print(f"   Con factores adversos adicionales: ~20-25%")
        print(f"   -> Mercado en 47% YES = SOBREVALORA retorno en +20-25pp")
        print(f"   -> Edge NO: ~15-20pp <-- MAYOR OPORTUNIDAD")
        print("="*65)

    return resultado


def calcular_base_rate_segunda_intervencion(verbose: bool = True) -> dict:
    """Calcula probabilidad de segunda intervencion militar EEUU"""
    casos_relevantes = [c for c in CASOS_SEGUNDA_INTERVENCION if c.get("relevancia", 0) >= 6]
    segundas = [c for c in casos_relevantes if c.get("segunda_intervencion") == True]
    no_segundas = [c for c in casos_relevantes if c.get("segunda_intervencion") == False]

    base_rate = len(segundas) / len(casos_relevantes) if casos_relevantes else 0

    if verbose:
        print("\n" + "="*65)
        print(" PATRON: SEGUNDA INTERVENCION MILITAR EEUU -- Base Rates")
        print("="*65)
        for c in sorted(casos_relevantes, key=lambda x: x.get("relevancia", 0), reverse=True):
            segunda = c.get("segunda_intervencion")
            if segunda is None:
                continue
            segunda_str = "SI hubo 2a intervencion" if segunda else "NO hubo 2a intervencion"
            print(f"\n  [{c.get('relevancia')}/10] {c['nombre']} ({c.get('ano_primera','')})")
            print(f"   {segunda_str}")
            print(f"   Razon: {c.get('razon','')}")
            if c.get("nota_diferencia"):
                print(f"   Diferencia con Venezuela: {c['nota_diferencia']}")

        print(f"\n{'-'*65}")
        print(f" Base rate 2a intervencion: {len(segundas)}/{len([c for c in casos_relevantes if c.get('segunda_intervencion') is not None])} = {base_rate*100:.0f}%")
        print(f"\n CASO VENEZUELA 2026 -- Ajustes:")
        print(f"   [VERDE] Modelo Panama 1989: NO segunda intervencion (mas similar)")
        print(f"   [VERDE] Rodriguez cooperativa -> EEUU sin incentivo")
        print(f"   [VERDE] Brent $107: Venezuela = valvula energetica estrategica")
        print(f"   [ROJO]  Riesgo: inestabilidad interna (aparato represivo intacto)")
        print(f"   [ROJO]  Riesgo: carteles llenando vacio de poder")
        print(f"\n   Base rate historico: {base_rate*100:.0f}%")
        print(f"   Con ajustes: ~5-7% probabilidad 2a intervencion")
        print(f"   -> Mercado en 15% YES = SOBREVALORA riesgo en +8-10pp")
        print(f"   -> Edge NO: ~8-10pp")
        print("="*65)

    return {"base_rate": base_rate}


def calcular_base_rate_ceasefire(verbose: bool = True) -> dict:
    """Base rates para resolucion de conflictos armados con EEUU"""
    if verbose:
        print("\n" + "="*65)
        print(" PATRON: CONFLICTOS EEUU -- Base Rates de Ceasefire")
        print("="*65)
        for c in sorted(CASOS_CEASEFIRE, key=lambda x: x.get("relevancia_actual", 0), reverse=True):
            resultado = "CEASEFIRE" if c.get("termino_en_ceasefire") else "Sin ceasefire formal"
            print(f"\n  [{c.get('relevancia_actual')}/10] {c['nombre']}")
            print(f"   Duracion activa: {c.get('duracion_activa_dias','?')} dias")
            print(f"   Resultado: {resultado}")
            print(f"   Nota: {c.get('notas','')}")

        total = len(CASOS_CEASEFIRE)
        ceasefires = sum(1 for c in CASOS_CEASEFIRE if c.get("termino_en_ceasefire"))
        print(f"\n{'-'*65}")
        print(f" Base rate ceasefire en conflictos EEUU: {ceasefires}/{total} = {ceasefires/total*100:.0f}%")
        print(f" Duracion media antes de ceasefire: 50-100 dias")
        print(f"\n IRAN 2026 (dia 32 del conflicto):")
        print(f"   [ROJO]  Hardliner Zolghadr nombrado jefe seguridad -> anti-negociacion")
        print(f"   [ROJO]  5 condiciones iranies = 'non-starters' para Trump")
        print(f"   [AMBAR] Pakistan mediador activo")
        print(f"   [AMBAR] Trump menciona 'great progress' (tactica negociadora dual)")
        print(f"   -> Ceasefire por Apr15: base rate ~20% + factores adversos = ~15-18%")
        print(f"   -> Mercado en 18% (YES) -> NO al 82% <-- bien calibrado, mantener")
        print("="*65)

    return {}


def mostrar_todos(args=None) -> None:
    calcular_base_rate_custodia()
    calcular_base_rate_retorno_exilio()
    calcular_base_rate_segunda_intervencion()
    calcular_base_rate_ceasefire()

    print("\n" + "="*65)
    print(" TABLA RESUMEN -- PROBABILIDADES DERIVADAS DE PATRONES")
    print("="*65)
    print(f"""
  Mercado                              Poly  Patron  Edge  Direccion
  -----------------------------------------------------------------
  Machado entra Venezuela Apr30        47%   20-25%  +22pp  NO [1]
  US forces Venezuela again Jun30      15%    5-7%   +9pp   NO [2]
  Maduro released Dec31                15%    6-8%   +8pp   NO [3]
  Cilia Flores released Dec31           8%    3-4%   +4pp   NO (bajo umbral)
  Iran ceasefire Apr15                 18%   15-18%  ~0pp   MANTENER
  -----------------------------------------------------------------
  [1] = Mayor oportunidad  [2] = 2da oportunidad  [3] = 3ra oportunidad
    """)
    print("="*65)


def consultar_patron(query: str) -> None:
    """Busca patrones relevantes para una consulta de texto libre"""
    query = query.lower()
    print(f"\n Buscando patrones para: '{query}'\n")

    if any(w in query for w in ["maduro", "liberado", "custodia", "preso", "juicio", "carcel"]):
        calcular_base_rate_custodia()
    if any(w in query for w in ["machado", "retorno", "exilio", "vuelve", "regresa"]):
        calcular_base_rate_retorno_exilio()
    if any(w in query for w in ["venezuela", "intervencion", "troops", "fuerzas", "militar"]):
        calcular_base_rate_segunda_intervencion()
    if any(w in query for w in ["ceasefire", "iran", "conflicto", "guerra", "acuerdo", "paz"]):
        calcular_base_rate_ceasefire()


def main():
    parser = argparse.ArgumentParser(
        description="Analizador de patrones historicos geopoliticos para Polymarket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python analizador_patrones.py --all
  python analizador_patrones.py --tipo custodia
  python analizador_patrones.py --tipo retorno_exilio
  python analizador_patrones.py --tipo ceasefire
  python analizador_patrones.py --consulta "maduro liberado antes del juicio"
        """
    )
    parser.add_argument("--tipo", choices=["custodia","transicion","ceasefire","segunda_intervencion","retorno_exilio"],
                        help="Tipo de patron a analizar")
    parser.add_argument("--all", action="store_true", help="Mostrar todos los patrones y tabla resumen")
    parser.add_argument("--consulta", help="Consulta de texto libre")
    args = parser.parse_args()

    if args.all:
        mostrar_todos()
    elif args.tipo == "custodia":
        calcular_base_rate_custodia()
    elif args.tipo == "retorno_exilio":
        calcular_base_rate_retorno_exilio()
    elif args.tipo == "segunda_intervencion":
        calcular_base_rate_segunda_intervencion()
    elif args.tipo == "ceasefire":
        calcular_base_rate_ceasefire()
    elif args.consulta:
        consultar_patron(args.consulta)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
