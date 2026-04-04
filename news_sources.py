# -*- coding: utf-8 -*-
"""
news_sources.py — Configuración de fuentes y reglas de prioridad
para el sistema de monitorización de noticias.
"""

# ─── FUENTES RSS ──────────────────────────────────────────────────────────────

FEEDS = [
    # Geopolítica / Medio Oriente
    {"url": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",   "source": "BBC"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml",                  "source": "AlJazeera"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml","source": "NYTimes"},
    {"url": "https://feeds.reuters.com/reuters/topNews",                   "source": "Reuters"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml",              "source": "SkyNews"},
    # Energía / Petróleo
    {"url": "https://oilprice.com/rss/main",                              "source": "OilPrice"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",              "source": "Reuters-Business"},
]

# ─── REGLAS DE MERCADO Y PRIORIDAD ───────────────────────────────────────────
# Cada regla define: mercado, keywords que activan, prioridad resultante.
# Se evalúan en orden — la primera que coincide gana.

RULES = [
    # ── CRITICA: eventos que mueven el precio inmediatamente ─────────────────
    {
        "market":   "iran_ceasefire",
        "priority": "CRITICA",
        "any": ["ceasefire", "alto el fuego", "armistice", "peace deal",
                "iran agrees", "iran accepts", "negotiation breakthrough",
                "trump backs down", "us withdraws", "acuerdo iran"],
    },
    {
        "market":   "iran_conflict",
        "priority": "CRITICA",
        "any": ["nuclear strike", "hormuz closed", "hormuz blockade",
                "strait of hormuz", "oil embargo", "israel strikes iran",
                "iran missile", "us strikes iran", "iran nuclear"],
    },
    {
        "market":   "wti_oil",
        "priority": "CRITICA",
        "any": ["oil price spike", "wti surges", "crude above 120",
                "brent above 120", "oil supply cut", "opec emergency",
                "pipeline attack", "saudi aramco attack"],
    },
    {
        "market":   "iran_invasion",
        "priority": "CRITICA",
        "any": ["us ground troops iran", "invasion iran", "boots on the ground iran",
                "us military iran", "marines iran", "us invades iran"],
    },
    # ── ALTA: desarrollos significativos ─────────────────────────────────────
    {
        "market":   "iran_ceasefire",
        "priority": "ALTA",
        "any": ["trump iran", "iran talks", "iran negotiat", "us iran deal",
                "oman mediati", "qatar mediati", "iran diplomat",
                "sanctions lifted", "iran sanctions"],
    },
    {
        "market":   "iran_conflict",
        "priority": "ALTA",
        "any": ["iran attack", "iran strike", "houthi", "hezbollah",
                "iran escalat", "middle east war", "iran irgc",
                "iran military", "us carrier", "fifth fleet"],
    },
    {
        "market":   "wti_oil",
        "priority": "ALTA",
        "any": ["opec cut", "oil production", "wti crude", "brent crude",
                "oil price", "crude oil", "energy crisis", "oil supply",
                "oil demand", "petroleum", "gasoline prices"],
    },
    {
        "market":   "iran_invasion",
        "priority": "ALTA",
        "any": ["us iran military", "pentagon iran", "iran war",
                "us forces middle east", "aircraft carrier gulf",
                "troop deployment iran", "iran conflict escalat"],
    },
    # ── MEDIA: contexto relevante ─────────────────────────────────────────────
    {
        "market":   "iran_ceasefire",
        "priority": "MEDIA",
        "any": ["iran", "tehran", "khamenei", "rouhani", "raisi",
                "irgc", "revolutionary guard", "us sanctions iran"],
    },
    {
        "market":   "wti_oil",
        "priority": "MEDIA",
        "any": ["energy", "fossil fuel", "natural gas", "refinery",
                "oil market", "oil trader", "commodities"],
    },
    {
        "market":   "macro",
        "priority": "MEDIA",
        "any": ["federal reserve", "fed rate", "inflation", "recession",
                "dollar index", "treasury yield", "s&p 500 drop"],
    },
]

# Prioridad por defecto si ninguna regla coincide pero el texto
# contiene al menos una keyword general de seguimiento
FALLBACK_KEYWORDS = [
    "iran", "israel", "trump", "middle east", "oil", "wti", "brent",
    "hormuz", "saudi", "opec", "pentagon", "white house"
]
FALLBACK_PRIORITY = "BAJA"
