import os
import time
import requests
import feedparser
import yfinance as yf
import schedule
from datetime import datetime
from dotenv import load_dotenv

# Cargar credenciales desde tu archivo .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Memoria para no repetir noticias
noticias_enviadas = set()
precio_brent_anterior = None

# Detector de velocidad noticiosa (breaking news)
_velocidad_noticias = {}  # keyword -> lista de timestamps de menciones recientes

# Directorio de logs
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log_noticia(titulo, agencia, link, sesgo):
    """Guarda la noticia en archivo diario en lugar de enviar por Telegram"""
    hoy = datetime.now().strftime("%Y-%m-%d")
    ruta = os.path.join(LOG_DIR, f"noticias_{hoy}.txt")
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M')}] [{agencia}] {titulo}\n")
        f.write(f"  Sesgo: {sesgo} | {link}\n\n")

# ==========================================
# 1. DICCIONARIO DE AGENCIAS Y SESGOS
# ==========================================
FUENTES = {
    # FUENTES INDEPENDIENTES — sin financiacion estatal significativa
    "CNBC":          {"url": "https://www.cnbc.com/id/100727362/device/rss/rss.html", "bloque": "Independiente (Nivel A)"},
    "Guardian":      {"url": "https://www.theguardian.com/world/rss",                 "bloque": "Independiente (Nivel A)"},
    "BBC MidEast":   {"url": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml","bloque": "Occidental (Nivel B)"},
    "BBC Business":  {"url": "http://feeds.bbci.co.uk/news/business/rss.xml",         "bloque": "Occidental (Nivel B)"},
    "Al-Monitor":    {"url": "https://www.al-monitor.com/rss",                        "bloque": "Regional (Nivel B)"},
    "FT":            {"url": "https://www.ft.com/world?format=rss",                   "bloque": "Independiente (Nivel A)"},
    # EXCLUIDAS POR FINANCIACION ESTATAL: TASS, Xinhua, IRNA, RT, Press TV
}

PALABRAS_CLAVE = [
    "iran", "israel", "ceasefire", "tregua", "hormuz", "deal", "acuerdo",
    "strike", "nuclear", "sanctions", "brent", "oil price", "kharg",
    "houthi", "red sea", "trump", "negotiate", "peace", "war", "attack",
    "invasion", "escalat", "regime", "pakistan", "ground troops"
]

# ==========================================
# 2. FUNCIONES PRINCIPALES
# ==========================================
def enviar_telegram(mensaje):
    """Envía el mensaje a tu móvil"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    datos = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, data=datos)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def analizar_sesgo(bloque):
    """Añade la advertencia crítica según el origen"""
    if "Estatal" in bloque:
        return "🔴 <b>ALERTA PROPAGANDA:</b> Medio controlado por el Estado. Consumo externo. Buscar confirmación cruzada."
    elif "Occidente" in bloque:
        return "🔵 <b>SESGO OCCIDENTAL:</b> Riesgo de 'narrativa de guerra' o visión pro-EEUU. Evaluar con cautela."
    elif "Oriente Medio" in bloque:
        return "🟡 <b>SESGO REGIONAL:</b> Buena info sobre el terreno, pero intereses directos implicados."
    return ""

def revisar_noticias():
    """
    Busca noticias nuevas en todas las agencias.
    MODO SILENCIOSO: guarda en log diario. Solo alerta Telegram si
    2 o más fuentes distintas confirman el mismo evento en el mismo ciclo.
    """
    print("Buscando noticias en Occidente y BRICS...")
    nuevas_por_keyword = {}  # keyword -> lista de agencias que la mencionan

    for nombre_agencia, datos in FUENTES.items():
        try:
            feed = feedparser.parse(datos["url"])
            for entrada in feed.entries[:5]:
                titulo = entrada.title
                link = entrada.link

                if any(palabra in titulo.lower() for palabra in PALABRAS_CLAVE):
                    if link not in noticias_enviadas:
                        sesgo = analizar_sesgo(datos["bloque"])
                        log_noticia(titulo, nombre_agencia, link, sesgo)
                        noticias_enviadas.add(link)
                        print(f"  [Log] {nombre_agencia}: {titulo[:50]}...")

                        # Detector de velocidad — breaking news si 4+ menciones en <30 min
                        import time as _time
                        ahora_ts = _time.time()
                        for kw in PALABRAS_CLAVE:
                            if kw in titulo.lower():
                                _velocidad_noticias.setdefault(kw, [])
                                _velocidad_noticias[kw].append(ahora_ts)
                                # Limpiar menciones de más de 30 min
                                _velocidad_noticias[kw] = [t for t in _velocidad_noticias[kw] if ahora_ts - t < 1800]
                                # Breaking news si 4+ fuentes en 30 min
                                if len(_velocidad_noticias[kw]) >= 4:
                                    enviar_telegram(
                                        f"🔴 <b>BREAKING NEWS — VELOCIDAD ALTA</b>\n"
                                        f"Keyword '<b>{kw.upper()}</b>' aparece {len(_velocidad_noticias[kw])}x en 30 min\n"
                                        f"Última noticia: {titulo[:80]}\n\n"
                                        f"⚡ Posible evento de mercado en curso."
                                    )
                                    _velocidad_noticias[kw] = []  # reset para no repetir

                        # Rastrear confirmaciones cruzadas
                        for kw in PALABRAS_CLAVE:
                            if kw in titulo.lower():
                                if kw not in nuevas_por_keyword:
                                    nuevas_por_keyword[kw] = []
                                nuevas_por_keyword[kw].append(
                                    {"agencia": nombre_agencia, "titulo": titulo,
                                     "sesgo": sesgo, "link": link}
                                )
        except Exception:
            pass

    # Solo enviar Telegram si 2+ fuentes distintas confirman el mismo evento
    for kw, fuentes_list in nuevas_por_keyword.items():
        if len(fuentes_list) >= 2:
            agencias_unicas = list({f["agencia"] for f in fuentes_list})
            mensaje  = f"🚨 <b>CONFIRMACION CRUZADA: '{kw.upper()}'</b>\n"
            mensaje += f"<i>{len(agencias_unicas)} fuentes distintas en el mismo ciclo</i>\n\n"
            for f in fuentes_list[:3]:
                mensaje += f"• <b>{f['agencia']}</b>: {f['titulo'][:70]}\n"
            mensaje += f"\n⚠️ Verificar impacto en posiciones."
            enviar_telegram(mensaje)
            print(f"  [ALERTA CRUZADA] {kw} confirmado por {agencias_unicas}")

def revisar_petroleo():
    """Vigila caídas bruscas del Brent (señal de ceasefire)"""
    global precio_brent_anterior
    try:
        print("Revisando mercado de petróleo...")
        brent = yf.Ticker("BZ=F")
        precio_actual = brent.fast_info['last_price']

        if precio_brent_anterior is not None:
            variacion = ((precio_actual - precio_brent_anterior) / precio_brent_anterior) * 100
            # Umbral subido a 4%: solo movimientos realmente significativos
            if variacion <= -4.0:
                mensaje = (f"🛢️ <b>ALERTA BRENT — CAIDA FUERTE</b>\n"
                           f"Caída: <b>{variacion:.1f}%</b> en una sesión\n"
                           f"Precio: <b>${precio_actual:.2f}</b>\n\n"
                           f"⚠️ Señal macro de distensión. Revisa posiciones NO.")
                enviar_telegram(mensaje)
            elif variacion >= 4.0:
                mensaje = (f"🛢️ <b>ALERTA BRENT — SUBIDA FUERTE</b>\n"
                           f"Subida: <b>+{variacion:.1f}%</b> en una sesión\n"
                           f"Precio: <b>${precio_actual:.2f}</b>\n\n"
                           f"✅ Señal macro de escalada. Refuerza posiciones NO.")

        precio_brent_anterior = precio_actual
    except Exception as e:
        print("No se pudo obtener el precio del petróleo ahora mismo.")

# ==========================================
# 3. BUCLE DE EJECUCIÓN CONTINUA
# ==========================================
def trabajo_rutinario():
    revisar_noticias()
    revisar_petroleo()
    print("-" * 40)

if __name__ == "__main__":
    print("INICIANDO BOT DE INTELIGENCIA GEOPOLITICA (modo silencioso)...")
    print("  - Noticias: guardadas en logs/noticias_HOY.txt")
    print("  - Telegram: solo si 2+ fuentes confirman el mismo evento")
    print("  - Brent: alerta solo si movimiento >= 4%")

    # Ejecutar la primera vez inmediatamente
    trabajo_rutinario()

    # Programar para que se ejecute cada 15 minutos (era 10)
    schedule.every(15).minutes.do(trabajo_rutinario)

    while True:
        schedule.run_pending()
        time.sleep(1)
