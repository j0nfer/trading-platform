"""
fuentes_avanzadas.py — Agregador avanzado de inteligencia multi-fuente
25+ fuentes organizadas por especialidad temática y nivel de fiabilidad.

Uso:
  python -X utf8 fuentes_avanzadas.py --iran          # noticias Iran
  python -X utf8 fuentes_avanzadas.py --venezuela     # noticias Venezuela
  python -X utf8 fuentes_avanzadas.py --macro         # macro/oil/mercados
  python -X utf8 fuentes_avanzadas.py --all           # todas las fuentes TOP10
  python -X utf8 fuentes_avanzadas.py --divergencia   # detectar narrativas opuestas
  python -X utf8 fuentes_avanzadas.py --test          # test sin API externa
"""

import argparse
import datetime
import json
import re
import sys
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

# ─── TAXONOMÍA DE FUENTES (25+) ──────────────────────────────────────────────
# Nivel A: Think tanks / académicos independientes
# Nivel B1: Grandes occidentales verificados
# Nivel B2: Regionales independientes con acceso de terreno
# Nivel C: Estatales con sesgo conocido (monitorizar narrativa oficial solamente)

FUENTES = {
    # ── THINK TANKS / NIVEL A ──────────────────────────────────────────────
    "ICG": {
        "url": "https://www.crisisgroup.org/rss.xml",
        "nivel": "A",
        "especialidad": ["iran", "venezuela", "conflictos", "ceasefire"],
        "peso": 4,
        "descripcion": "International Crisis Group — mejor fuente mundial de análisis de conflictos",
        "cobertura": "Global",
        "sesgo": "Ninguno conocido — metodología académica rigurosa",
    },
    "Chatham House": {
        "url": "https://www.chathamhouse.org/rss.xml",
        "nivel": "A",
        "especialidad": ["iran", "geopolitica", "energia", "oriente_medio"],
        "peso": 4,
        "descripcion": "Think tank independiente británico — análisis profundo geopolítico",
        "cobertura": "Global con foco en energy security",
        "sesgo": "Ligero pro-occidental pero metodológicamente sólido",
    },
    "Atlantic Council": {
        "url": "https://www.atlanticcouncil.org/feed/",
        "nivel": "A",
        "especialidad": ["iran", "venezuela", "eeuu", "geopolitica"],
        "peso": 3,
        "descripcion": "Think tank EEUU — muy relevante para política exterior americana",
        "cobertura": "Global con foco EEUU",
        "sesgo": "Pro-atlantista, pero análisis técnico sólido",
    },
    "RAND Corporation": {
        "url": "https://www.rand.org/pubs/rss/recent-research.xml",
        "nivel": "A",
        "especialidad": ["iran", "eeuu_militar", "seguridad"],
        "peso": 4,
        "descripcion": "Laboratorio de ideas del Pentágono — análisis estratégico máximo nivel",
        "cobertura": "Seguridad y defensa global",
        "sesgo": "Pro-EEUU implícito pero metodología cuantitativa rigurosa",
    },
    "Wilson Center": {
        "url": "https://www.wilsoncenter.org/rss.xml",
        "nivel": "A",
        "especialidad": ["venezuela", "latinoamerica", "iran"],
        "peso": 3,
        "descripcion": "Think tank académico EEUU — mejor cobertura de América Latina",
        "cobertura": "América Latina + Oriente Medio",
        "sesgo": "Ligero pro-democracia occidental",
    },

    # ── AGENCIAS / NIVEL B1 ────────────────────────────────────────────────
    "Reuters World": {
        "url": "https://feeds.reuters.com/reuters/worldNews",
        "nivel": "B1",
        "especialidad": ["iran", "venezuela", "macro", "oil", "general"],
        "peso": 3,
        "descripcion": "Agencia de mayor credibilidad — estándar de verificación de hechos",
        "cobertura": "Global",
        "sesgo": "Pro-occidental leve, pero hechos bien verificados",
    },
    "Reuters Business": {
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "nivel": "B1",
        "especialidad": ["macro", "oil", "mercados", "sanciones"],
        "peso": 3,
        "descripcion": "Reuters — mejor fuente para oil markets y sanciones económicas",
        "cobertura": "Business/finanzas global",
        "sesgo": "Neutral en finanzas",
    },
    "AP News": {
        "url": "https://rsshub.app/apnews/topics/apf-topnews",
        "nivel": "B1",
        "especialidad": ["general", "iran", "eeuu"],
        "peso": 3,
        "descripcion": "Associated Press — máxima fiabilidad en breaking news",
        "cobertura": "Global",
        "sesgo": "Pro-occidental muy leve",
    },
    "FT": {
        "url": "https://www.ft.com/rss/home",
        "nivel": "B1",
        "especialidad": ["macro", "oil", "iran", "mercados", "sanciones"],
        "peso": 3,
        "descripcion": "Financial Times — mejor análisis financiero-geopolítico",
        "cobertura": "Global con foco mercados",
        "sesgo": "[FUENTE C aplicable para análisis de mercado] — pro-establishment financiero",
    },
    "BBC World": {
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "nivel": "B1",
        "especialidad": ["iran", "venezuela", "general"],
        "peso": 3,
        "descripcion": "BBC — cobertura internacional amplia y verificada",
        "cobertura": "Global",
        "sesgo": "Pro-occidental moderado",
    },
    "Guardian World": {
        "url": "https://www.theguardian.com/world/rss",
        "nivel": "B1",
        "especialidad": ["iran", "venezuela", "geopolitica"],
        "peso": 3,
        "descripcion": "Guardian — excelente cobertura de derechos humanos y geopolítica",
        "cobertura": "Global con foco en DDHH",
        "sesgo": "Centro-izquierda moderado",
    },

    # ── ESPECIALIZADOS IRAN / NIVEL B2 ─────────────────────────────────────
    "Al-Monitor": {
        "url": "https://www.al-monitor.com/rss.xml",
        "nivel": "B2",
        "especialidad": ["iran", "oriente_medio", "israel"],
        "peso": 3,
        "descripcion": "La mejor fuente sobre política interna iraní y árabe — periodistas en terreno",
        "cobertura": "Oriente Medio — mejor en su categoría para Iran",
        "sesgo": "Pro-árabe moderado, equilibrado en Iran",
    },
    "Times of Israel": {
        "url": "https://www.timesofisrael.com/feed/",
        "nivel": "B2",
        "especialidad": ["iran", "israel", "oriente_medio"],
        "peso": 2,
        "descripcion": "Perspectiva israelí — esencial para entender posición Israel en conflicto Iran",
        "cobertura": "Israel + región",
        "sesgo": "Pro-Israel moderado",
    },
    "Haaretz": {
        "url": "https://www.haaretz.com/cmlink/1.628765",
        "nivel": "B2",
        "especialidad": ["iran", "israel", "politica_interna_israel"],
        "peso": 3,
        "descripcion": "El periódico israelí más crítico — útil para oposición interna a Netanyahu",
        "cobertura": "Israel + geopolítica regional",
        "sesgo": "Centro-izquierda israelí — contrapeso a Times of Israel",
    },
    "Middle East Eye": {
        "url": "https://www.middleeasteye.net/rss",
        "nivel": "B2",
        "especialidad": ["iran", "oriente_medio", "houthis"],
        "peso": 2,
        "descripcion": "Perspectiva árabe independiente — buena cobertura de terreno",
        "cobertura": "Oriente Medio",
        "sesgo": "Pro-árabe moderado",
    },
    "Radio Farda": {
        "url": "https://www.radiofarda.com/api/ztyqoeuori",
        "nivel": "B2",
        "especialidad": ["iran_interno", "iran"],
        "peso": 3,
        "descripcion": "Servicio persa de Radio Free Europe — única fuente de perspectiva interna iraní",
        "cobertura": "Iran exclusivamente — perspectiva interna",
        "sesgo": "Pro-oposición iraní (financiado por Congreso EEUU) — marcar si análisis político",
    },

    # ── ESPECIALIZADOS VENEZUELA/LATAM / NIVEL B2 ──────────────────────────
    "Americas Quarterly": {
        "url": "https://www.americasquarterly.org/feed/",
        "nivel": "B2",
        "especialidad": ["venezuela", "latinoamerica", "politica_regional"],
        "peso": 3,
        "descripcion": "La mejor publicación de análisis político latinoamericano",
        "cobertura": "América Latina — top en Venezuela",
        "sesgo": "Pro-democracia moderado",
    },
    "InSight Crime": {
        "url": "https://insightcrime.org/feed/",
        "nivel": "B2",
        "especialidad": ["venezuela", "narcotrafico", "crimen_organizado", "maduro"],
        "peso": 3,
        "descripcion": "La mejor fuente sobre crimen organizado en América Latina — esencial para caso Maduro",
        "cobertura": "Crimen organizado Latam — imprescindible",
        "sesgo": "Ninguno conocido — periodismo de investigación",
    },
    "LADB (Latin America DB)": {
        "url": "https://ladb.unm.edu/rss.xml",
        "nivel": "B2",
        "especialidad": ["latinoamerica", "venezuela"],
        "peso": 2,
        "descripcion": "Base de datos académica Latam — análisis de largo plazo",
        "cobertura": "América Latina académico",
        "sesgo": "Académico neutral",
    },

    # ── MACRO / ENERGÍA / NIVEL B1-B2 ─────────────────────────────────────
    "CNBC Energy": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19836768",
        "nivel": "B1",
        "especialidad": ["oil", "brent", "macro", "iran"],
        "peso": 3,
        "descripcion": "CNBC Energy — mejor cobertura rápida de movimientos de oil",
        "cobertura": "Energía y commodities",
        "sesgo": "Pro-mercado, [FUENTE C en análisis de inversión]",
    },
    "IEA News": {
        "url": "https://www.iea.org/news/rss",
        "nivel": "A",
        "especialidad": ["oil", "energia", "iran", "venezuela"],
        "peso": 4,
        "descripcion": "Agencia Internacional de Energía — datos de oil más fiables del mundo",
        "cobertura": "Energía global — NIVEL A en commodities",
        "sesgo": "Pro-OCDE leve, pero datos verificables",
    },
    "EIA (US Energy Info)": {
        "url": "https://www.eia.gov/rss/news.xml",
        "nivel": "A",
        "especialidad": ["oil", "brent", "venezuela_oil", "iran_oil"],
        "peso": 4,
        "descripcion": "Administración de Información Energética EEUU — estadísticas primarias",
        "cobertura": "Energía EEUU + global",
        "sesgo": "Datos puros — pro-EEUU en análisis",
    },
    "NPR World": {
        "url": "https://feeds.npr.org/1004/rss.xml",
        "nivel": "B1",
        "especialidad": ["iran", "eeuu", "venezuela", "general"],
        "peso": 2,
        "descripcion": "NPR — perspectiva EEUU equilibrada",
        "cobertura": "Global con foco EEUU",
        "sesgo": "Centro-izquierda moderado EEUU",
    },
    "Foreign Policy": {
        "url": "https://foreignpolicy.com/feed/",
        "nivel": "B1",
        "especialidad": ["iran", "venezuela", "geopolitica", "doctrina_trump"],
        "peso": 3,
        "descripcion": "Foreign Policy — análisis profundo de política exterior EEUU",
        "cobertura": "Política exterior global",
        "sesgo": "Think tank liberal-internacionalista",
    },
    "Politico Foreign": {
        "url": "https://www.politico.com/rss/politics08.xml",
        "nivel": "B1",
        "especialidad": ["eeuu", "trump", "sanchez", "congreso"],
        "peso": 2,
        "descripcion": "Politico — mejor cobertura de decisiones políticas EEUU",
        "cobertura": "Política EEUU",
        "sesgo": "Centro moderado EEUU",
    },

    # ── MONITORIZAR (NIVEL C — solo narrativa oficial) ────────────────────
    "TASS": {
        "url": "https://tass.com/rss/v2.xml",
        "nivel": "C",
        "especialidad": ["iran", "venezuela", "rusia"],
        "peso": 0,  # NO usar en análisis, solo monitorizar
        "descripcion": "NIVEL C — Agencia estatal rusa. Solo para leer narrativa oficial Kremlin.",
        "cobertura": "Pro-Rusia",
        "sesgo": "PROPAGANDA ESTATAL — marcar siempre como [FUENTE C]",
    },
    "PressTV": {
        "url": "https://www.presstv.ir/rss",
        "nivel": "C",
        "especialidad": ["iran_oficial"],
        "peso": 0,
        "descripcion": "NIVEL C — Televisión estatal iraní. Solo narrativa oficial Teherán.",
        "cobertura": "Narrativa oficial iraní",
        "sesgo": "PROPAGANDA ESTATAL IRANÍ — marcar siempre",
    },
}

# ── KEYWORDS POR TEMA ────────────────────────────────────────────────────────
KEYWORDS_IRAN = [
    "iran", "iranian", "tehran", "khamenei", "mojtaba", "irgc", "hormuz", "strait",
    "ceasefire", "nuclear", "sanctions", "trump iran", "strikes iran", "houthi",
    "pakistan mediat", "zolghadr", "kharg", "bushehr", "uranium",
]
KEYWORDS_VENEZUELA = [
    "venezuela", "maduro", "rodriguez", "delcy", "machado", "chavez", "pdvsa",
    "caracas", "bolivar", "guaido", "narco", "custody", "brooklyn", "interina",
    "operación absolute", "citgo", "maracaibo",
]
KEYWORDS_MACRO = [
    "brent", "wti", "crude oil", "opec", "fed rate", "inflation", "vix", "gold",
    "recession", "gdp", "oil price", "energy market", "petroleum",
]
KEYWORDS_TRUMP_DOCTRINA = [
    "trump regime", "regime change", "absolute resolve", "donroe", "intervention",
    "cuba sanctions", "colombia trump", "greenland", "panama canal",
]

HOY = datetime.date.today()


def parsear_fecha(entry) -> datetime.datetime:
    """Extrae y parsea la fecha de una entrada RSS"""
    for campo in ["published_parsed", "updated_parsed"]:
        t = getattr(entry, campo, None)
        if t:
            try:
                return datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc)
            except:
                pass
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)


def calcular_score_noticia(titulo: str, fuente_key: str, fecha: datetime.datetime,
                            keywords_activos: list) -> dict:
    """Puntúa una noticia de 0-20 para ranking de relevancia"""
    fuente = FUENTES.get(fuente_key, {})
    peso_fuente = fuente.get("peso", 1)
    nivel = fuente.get("nivel", "B2")

    # Score base por nivel
    nivel_score = {"A": 5, "B1": 4, "B2": 3, "C": 0}.get(nivel, 2)

    # Score por keywords
    titulo_lower = titulo.lower()
    kw_hits = sum(1 for kw in keywords_activos if kw.lower() in titulo_lower)
    kw_score = min(kw_hits * 2, 8)  # max 8 pts por keywords

    # Score por frescura
    ahora = datetime.datetime.now(datetime.timezone.utc)
    horas = (ahora - fecha.replace(tzinfo=datetime.timezone.utc) if fecha.tzinfo is None else ahora - fecha).total_seconds() / 3600
    if horas < 3:
        fresh_score = 4
    elif horas < 12:
        fresh_score = 3
    elif horas < 24:
        fresh_score = 2
    elif horas < 48:
        fresh_score = 0
    else:
        fresh_score = -2

    total = nivel_score + kw_score + fresh_score
    return {
        "total": max(0, total),
        "nivel_score": nivel_score,
        "kw_score": kw_score,
        "fresh_score": fresh_score,
        "horas_edad": horas,
    }


def impacto_portfolio(titulo: str) -> str:
    """Determina impacto en portfolio Iran/Venezuela"""
    t = titulo.lower()
    # Iran NO reforzado
    if any(w in t for w in ["no ceasefire", "escalat", "attack", "strike", "missile", "refuses", "reject"]):
        return "Refuerza NO ceasefire"
    # Iran YES (riesgo para posición NO)
    if any(w in t for w in ["ceasefire", "agreement", "deal", "peace", "negotiate", "talks", "mediat"]):
        return "Riesgo: señal pro-ceasefire"
    # Venezuela NO reforzado
    if any(w in t for w in ["maduro trial", "no release", "rodriguez stable", "diplomatic"]):
        return "Refuerza NO Venezuela"
    # Venezuela YES (riesgo)
    if any(w in t for w in ["machado return", "maduro release", "us troops", "intervention"]):
        return "Monitorizar: afecta Venezuela bets"
    # Brent
    if any(w in t for w in ["brent", "crude oil", "oil price", "opec"]):
        return "Impacto macro (verificar dirección)"
    return "Neutral portfolio"


def fetch_fuente(key: str, fuente: dict, keywords: list, max_items: int = 10) -> list:
    """Descarga y parsea un feed RSS"""
    if not HAS_FEEDPARSER:
        return []
    if fuente.get("peso", 0) == 0:
        return []  # Skip nivel C en análisis normal

    noticias = []
    try:
        feed = feedparser.parse(fuente["url"])
        for entry in feed.entries[:max_items]:
            titulo = getattr(entry, "title", "Sin título")
            link   = getattr(entry, "link", "")
            fecha  = parsear_fecha(entry)
            score  = calcular_score_noticia(titulo, key, fecha, keywords)

            if score["total"] > 0:
                noticias.append({
                    "titulo": titulo,
                    "fuente": key,
                    "nivel": fuente.get("nivel", "B2"),
                    "link": link,
                    "fecha": fecha.isoformat(),
                    "score": score["total"],
                    "score_detalle": score,
                    "impacto": impacto_portfolio(titulo),
                })
    except Exception as e:
        pass

    return noticias


def fetch_tema(tema: str, top_n: int = 10) -> None:
    """Descarga todas las fuentes especializadas en un tema y muestra top N"""
    keywords_map = {
        "iran":      KEYWORDS_IRAN,
        "venezuela": KEYWORDS_VENEZUELA,
        "macro":     KEYWORDS_MACRO,
        "trump":     KEYWORDS_TRUMP_DOCTRINA,
    }
    keywords = keywords_map.get(tema.lower(), KEYWORDS_IRAN + KEYWORDS_VENEZUELA)

    # Filtrar fuentes especializadas en el tema
    fuentes_tema = {k: v for k, v in FUENTES.items()
                    if tema.lower() in [e.lower() for e in v.get("especialidad", [])]}

    if not fuentes_tema:
        fuentes_tema = {k: v for k, v in FUENTES.items() if v.get("peso", 0) > 0}

    print(f"\n{'='*65}")
    print(f" INTELIGENCIA -- {tema.upper()} | {len(fuentes_tema)} fuentes especializadas")
    print(f" {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    if not HAS_FEEDPARSER:
        print("\n  feedparser no instalado. Ejecuta: pip install feedparser")
        print(" Fuentes configuradas para este tema:")
        for k, v in sorted(fuentes_tema.items(), key=lambda x: x[1]["peso"], reverse=True):
            print(f"   [{v['nivel']}][peso:{v['peso']}] {k}: {v['descripcion']}")
        return

    todas_noticias = []
    for key, fuente in fuentes_tema.items():
        noticias = fetch_fuente(key, fuente, keywords)
        todas_noticias.extend(noticias)

    # Deduplicar por título similar
    vistos = set()
    dedup = []
    for n in todas_noticias:
        titulo_norm = n["titulo"].lower()[:60]
        if titulo_norm not in vistos:
            vistos.add(titulo_norm)
            dedup.append(n)

    # Ordenar por score
    dedup.sort(key=lambda x: x["score"], reverse=True)
    top = dedup[:top_n]

    if not top:
        print(f"\n No se encontraron noticias relevantes de {tema}")
        print(f" (Normal si las fuentes están vacías o no hay keywords en títulos recientes)")
        return

    print(f"\n TOP {len(top)} NOTICIAS -- {tema.upper()}")
    print(f"{'-'*65}")
    for i, n in enumerate(top, 1):
        horas = n["score_detalle"]["horas_edad"]
        tiempo_str = f"{horas:.0f}h" if horas < 48 else f"{horas/24:.0f}d"
        print(f"\n {i}. [{n['nivel']}][score:{n['score']}] {n['fuente']} -- hace {tiempo_str}")
        print(f"    {n['titulo']}")
        print(f"    {n['impacto']}")
        if n.get("link"):
            print(f"    -> {n['link'][:80]}")

    # Análisis de divergencia narrativa
    fuentes_usadas = set(n["fuente"] for n in top)
    niveles = [FUENTES[f]["nivel"] for f in fuentes_usadas if f in FUENTES]
    confirmacion = sum(1 for l in niveles if l in ["A", "B1"])

    print(f"\n{'-'*65}")
    print(f" ANALISIS DE CONFIRMACION CRUZADA:")
    print(f"   Fuentes nivel A/B1 confirmando: {confirmacion}")
    if confirmacion >= 2:
        print(f"   2+ fuentes independientes A/B1 -> Alta fiabilidad")
    else:
        print(f"   < 2 fuentes A/B1 -> Baja fiabilidad -- buscar confirmación")
    print(f"{'='*65}\n")


def mostrar_taxonomia() -> None:
    """Muestra la taxonomía completa de fuentes"""
    print(f"\n{'='*65}")
    print(f" TAXONOMIA DE FUENTES -- {len(FUENTES)} fuentes configuradas")
    print(f"{'='*65}")

    for nivel in ["A", "B1", "B2", "C"]:
        fuentes_nivel = {k: v for k, v in FUENTES.items() if v["nivel"] == nivel}
        if not fuentes_nivel:
            continue
        etiquetas = {"A": "NIVEL A -- Think Tanks / Académico", "B1": "NIVEL B1 -- Grandes Occidentales",
                     "B2": "NIVEL B2 -- Especializados Regionales", "C": "NIVEL C -- Estatales (solo narrativa)"}
        print(f"\n {'-'*60}")
        print(f" {etiquetas.get(nivel, nivel)}")
        print(f" {'-'*60}")
        for k, v in sorted(fuentes_nivel.items(), key=lambda x: x[1]["peso"], reverse=True):
            especialidades = ", ".join(v.get("especialidad", [])[:3])
            print(f"   [{v['peso']}/4] {k:<20} | {especialidades}")
            print(f"         {v['descripcion'][:55]}")


def detectar_divergencia() -> None:
    """Detecta cuando fuentes de bloques opuestos tienen narrativas divergentes"""
    print(f"\n{'='*65}")
    print(f" DETECTOR DE DIVERGENCIA NARRATIVA")
    print(f" Compara fuentes pro-Occidente vs pro-Oriente")
    print(f"{'='*65}")
    print(f"\n Fuentes pro-Occidente: Reuters, BBC, FT, Guardian, AP")
    print(f" Fuentes pro-Oriente/neutras: Al-Monitor, Middle East Eye, Radio Farda")
    print(f" Fuentes oficiales (C): TASS, PressTV")
    print(f"\n Metodología:")
    print(f"   1. Mismo evento cubierto en ambos bloques = VERIFICADO")
    print(f"   2. Evento solo en un bloque = POTENCIAL SESGO")
    print(f"   3. Narrativas contradictorias = ALERTA DE DESINFORMACION")
    print(f"\n Funcion manual -- leer fuentes de ambos bloques antes de decidir")
    print(f"{'='*65}")


def test_sin_api() -> None:
    """Muestra la configuración sin necesidad de feedparser"""
    print(f"\n{'='*65}")
    print(f" TEST -- fuentes_avanzadas.py")
    print(f"{'='*65}")
    print(f"\n Fuentes configuradas: {len(FUENTES)}")
    print(f" feedparser disponible: {HAS_FEEDPARSER}")

    total_A  = sum(1 for v in FUENTES.values() if v["nivel"] == "A")
    total_B1 = sum(1 for v in FUENTES.values() if v["nivel"] == "B1")
    total_B2 = sum(1 for v in FUENTES.values() if v["nivel"] == "B2")
    total_C  = sum(1 for v in FUENTES.values() if v["nivel"] == "C")

    print(f"\n Distribución por nivel:")
    print(f"   Nivel A  (Think tanks) : {total_A} fuentes")
    print(f"   Nivel B1 (Grandes occ) : {total_B1} fuentes")
    print(f"   Nivel B2 (Regionales)  : {total_B2} fuentes")
    print(f"   Nivel C  (Estatales)   : {total_C} fuentes (solo narrativa)")

    print(f"\n Especialidades cubiertas:")
    all_esp = set()
    for v in FUENTES.values():
        all_esp.update(v.get("especialidad", []))
    for esp in sorted(all_esp):
        count = sum(1 for v in FUENTES.values() if esp in v.get("especialidad", []))
        print(f"   {esp:<25}: {count} fuentes")

    if not HAS_FEEDPARSER:
        print(f"\n  Para activar descarga real: pip install feedparser")
    else:
        print(f"\n feedparser instalado -- listo para fetch real")

    print(f"\n{'='*65}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Agregador avanzado de inteligencia multi-fuente (25+ fuentes)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Temas disponibles: iran, venezuela, macro, trump
Ejemplos:
  python -X utf8 fuentes_avanzadas.py --iran
  python -X utf8 fuentes_avanzadas.py --venezuela
  python -X utf8 fuentes_avanzadas.py --macro
  python -X utf8 fuentes_avanzadas.py --all
  python -X utf8 fuentes_avanzadas.py --taxonomia
  python -X utf8 fuentes_avanzadas.py --test
        """
    )
    parser.add_argument("--iran",       action="store_true")
    parser.add_argument("--venezuela",  action="store_true")
    parser.add_argument("--macro",      action="store_true")
    parser.add_argument("--trump",      action="store_true")
    parser.add_argument("--all",        action="store_true", help="Todas las fuentes, top 10 global")
    parser.add_argument("--taxonomia",  action="store_true", help="Mostrar taxonomía completa")
    parser.add_argument("--divergencia",action="store_true", help="Guía de detección de divergencia narrativa")
    parser.add_argument("--test",       action="store_true", help="Test sin API")
    parser.add_argument("--top",        type=int, default=10, help="Número de noticias a mostrar")
    args = parser.parse_args()

    if args.test:
        test_sin_api()
    elif args.taxonomia:
        mostrar_taxonomia()
    elif args.divergencia:
        detectar_divergencia()
    elif args.iran:
        fetch_tema("iran", args.top)
    elif args.venezuela:
        fetch_tema("venezuela", args.top)
    elif args.macro:
        fetch_tema("macro", args.top)
    elif args.trump:
        fetch_tema("trump", args.top)
    elif args.all:
        fetch_tema("iran", 5)
        fetch_tema("venezuela", 5)
        fetch_tema("macro", 3)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
