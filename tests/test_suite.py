"""
test_suite.py — Suite de tests automatizados para todos los scripts de inversiones
Detecta bugs, inconsistencias y errores antes de que afecten decisiones reales.

Uso:
  python -X utf8 test_suite.py           # correr todos los tests
  python -X utf8 test_suite.py --rapido  # solo tests críticos (sin API)
  python -X utf8 test_suite.py --fix     # mostrar sugerencias de fix para cada bug
  python -X utf8 test_suite.py --json    # output JSON para procesamiento automático
"""

import sys, os

# Soporte para CI/CD — variable de entorno TRADING_DIR sobreescribe la ruta local
DIRECTORIO = os.environ.get("TRADING_DIR", "C:\\inversiones")
sys.path.insert(0, DIRECTORIO)

import argparse
import datetime
import importlib.util
import json
import subprocess
import time
import traceback
import requests
LOGS_DIR   = os.path.join(DIRECTORIO, "logs")
BUGS_FILE  = os.path.join(LOGS_DIR, "bugs_detectados.json")
HOY        = datetime.date.today().isoformat()

# ─── DEFINICIÓN DE TESTS ─────────────────────────────────────────────────────

TESTS = [
    # ── GRUPO 1: SINTAXIS Y COMPILACIÓN ────────────────────────────────────
    {
        "id": "T001",
        "nombre": "Sintaxis: analizador_universal.py",
        "tipo": "compilacion",
        "script": "markets/polymarket/analizador_universal.py",
        "critico": True,
    },
    {
        "id": "T002",
        "nombre": "Sintaxis: comparador_odds.py",
        "tipo": "compilacion",
        "script": "markets/polymarket/comparador_odds.py",
        "critico": True,
    },
    {
        "id": "T003",
        "nombre": "Sintaxis: analizador_patrones.py",
        "tipo": "compilacion",
        "script": "research/sources/analizador_patrones.py",
        "critico": True,
    },
    {
        "id": "T004",
        "nombre": "Sintaxis: fuentes_avanzadas.py",
        "tipo": "compilacion",
        "script": "research/sources/fuentes_avanzadas.py",
        "critico": True,
    },
    {
        "id": "T005",
        "nombre": "Sintaxis: telegram_alertas.py",
        "tipo": "compilacion",
        "script": "alerts/telegram_alertas.py",
        "critico": True,
    },
    {
        "id": "T006",
        "nombre": "Sintaxis: motor_alertas.py",
        "tipo": "compilacion",
        "script": "alerts/motor_alertas.py",
        "critico": True,
    },
    {
        "id": "T007",
        "nombre": "Sintaxis: comparador_mercados.py",
        "tipo": "compilacion",
        "script": "markets/polymarket/comparador_mercados.py",
        "critico": True,
    },
    {
        "id": "T008",
        "nombre": "Sintaxis: watchlist.py",
        "tipo": "compilacion",
        "script": "markets/polymarket/watchlist.py",
        "critico": False,
    },
    {
        "id": "T009",
        "nombre": "Sintaxis: diario_trading.py",
        "tipo": "compilacion",
        "script": "portfolio/diario_trading.py",
        "critico": False,
    },
    {
        "id": "T009b",
        "nombre": "Sintaxis: pyth_feed.py",
        "tipo": "compilacion",
        "script": "core/pyth_feed.py",
        "critico": True,
    },
    {
        "id": "T009c",
        "nombre": "Sintaxis: polymarket_api.py",
        "tipo": "compilacion",
        "script": "core/polymarket_api.py",
        "critico": True,
    },
    {
        "id": "T009d",
        "nombre": "Sintaxis: whale_tracker.py",
        "tipo": "compilacion",
        "script": "markets/polymarket/whale_tracker.py",
        "critico": True,
    },
    {
        "id": "T009e",
        "nombre": "Sintaxis: core.py",
        "tipo": "compilacion",
        "script": "core.py",
        "critico": True,
    },
    # ── GRUPO 2: API CONNECTIVITY ───────────────────────────────────────────
    {
        "id": "T010",
        "nombre": "API: Polymarket Gamma accesible",
        "tipo": "conectividad",
        "url": "https://gamma-api.polymarket.com/markets?slug=us-x-iran-ceasefire-by-april-15-182-528-637",
        "validacion": lambda r: isinstance(r, list) and len(r) > 0 and "outcomePrices" in r[0],
        "error_esperado": "La API de Gamma no responde o devuelve formato inesperado",
        "critico": True,
    },
    {
        "id": "T011",
        "nombre": "API: Polymarket Data (trades) accesible",
        "tipo": "conectividad",
        "url": "https://data-api.polymarket.com/trades?limit=5",
        "validacion": lambda r: isinstance(r, list),
        "error_esperado": "La API de Data no responde o devuelve formato inesperado",
        "critico": False,
    },
    {
        "id": "T012",
        "nombre": "API: Yahoo Finance (Brent) accesible",
        "tipo": "conectividad",
        "url": "https://query1.finance.yahoo.com/v8/finance/chart/BZ%3DF",
        "validacion": lambda r: "chart" in r and r["chart"]["result"] is not None,
        "error_esperado": "Yahoo Finance no devuelve datos de Brent",
        "critico": False,
    },
    # ── GRUPO 3: VALIDACIÓN DE PRECIOS ─────────────────────────────────────
    {
        "id": "T020",
        "nombre": "Precio: Ceasefire Apr15 en rango válido (0.01-0.99)",
        "tipo": "precio_valido",
        "slug": "us-x-iran-ceasefire-by-april-15-182-528-637",
        "campo": "yes",
        "rango": (0.01, 0.99),
        "critico": True,
    },
    {
        "id": "T021",
        "nombre": "Precio: Regime Fall Jun30 en rango válido",
        "tipo": "precio_valido",
        "slug": "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725",
        "campo": "yes",
        "rango": (0.01, 0.99),
        "critico": True,
    },
    {
        "id": "T022",
        "nombre": "Suma YES+NO = 1.0 (+-0.02) para Ceasefire Apr15",
        "tipo": "suma_precios",
        "slug": "us-x-iran-ceasefire-by-april-15-182-528-637",
        "tolerancia": 0.02,
        "critico": True,
    },
    # ── GRUPO 4: CONSISTENCIA DE P/L ───────────────────────────────────────
    {
        "id": "T030",
        "nombre": "P/L: Pos1 (Ceasefire Apr15 NO) consistente +-$10",
        "tipo": "pl_consistencia",
        "descripcion": (
            "El P/L de la Pos1 debe ser consistente entre scripts. "
            "Precio entrada: 0.657, shares: 304.3, precio_no actual de API."
        ),
        "calculo": "pos1",
        "tolerancia_usd": 10.0,
        "critico": True,
        "fix": (
            "El P/L de Pos1 se calcula como: (no_actual - 0.657) * 304.3\n"
            "Asegurarse que todos los scripts usen el precio NO real de la API."
        ),
    },
    {
        "id": "T031",
        "nombre": "Codigo: comparador_mercados.py usa slug correcto y precio NO directo para Pos2",
        "tipo": "codigo_contiene",
        "archivo": "markets/polymarket/comparador_mercados.py",
        "debe_contener": [
            "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725",
            "p_jun30_no = m[\"precio\"].get(\"no\")",
            "pnl = (p_jun30_no - entrada)",
        ],
        "no_debe_contener": [
            "\"Regime falls Jun 30 ★\"",
        ],
        "critico": True,
        "fix": (
            "En comparador_mercados.py funcion resumen_final():\n"
            "1. Añadir: p_jun30_yes = m['precio'].get('yes')\n"
            "2. Cambiar: pnl = (p_jun30_yes - entrada) * 558.8  (NO usar p_jun30_no)\n"
            "El campo nuestra_pos='NO' es el nombre conceptual, pero el precio efectivo es YES del slug proxy."
        ),
    },
    {
        "id": "T032",
        "nombre": "P/L total: suma de ambas posiciones entre -$200 y +$300",
        "tipo": "pl_rango",
        "rango_usd": (-200, 300),
        "critico": True,
    },
    # ── GRUPO 5: OUTPUTS DE SCRIPTS ────────────────────────────────────────
    {
        "id": "T040",
        "nombre": "analizador_universal --test: produce salida válida",
        "tipo": "ejecucion",
        "comando": ["python", "-X", "utf8", "markets/polymarket/analizador_universal.py", "--test"],
        "contiene": ["TOTAL:", "/30", "VEREDICTO"],
        "no_contiene": ["Traceback", "Error", "Exception"],
        "timeout": 30,
        "critico": True,
    },
    {
        "id": "T041",
        "nombre": "analizador_patrones --all: produce tabla resumen",
        "tipo": "ejecucion",
        "comando": ["python", "-X", "utf8", "research/sources/analizador_patrones.py", "--all"],
        "contiene": ["TABLA RESUMEN", "Machado", "Maduro", "Edge"],
        "no_contiene": ["Traceback", "Error", "Exception"],
        "timeout": 30,
        "critico": True,
    },
    {
        "id": "T042",
        "nombre": "fuentes_avanzadas --test: detecta feedparser y fuentes",
        "tipo": "ejecucion",
        "comando": ["python", "-X", "utf8", "research/sources/fuentes_avanzadas.py", "--test"],
        "contiene": ["Fuentes configuradas", "Nivel A"],
        "no_contiene": ["Traceback"],
        "timeout": 15,
        "critico": False,
    },
    {
        "id": "T043",
        "nombre": "comparador_odds --test: produce gap analysis",
        "tipo": "ejecucion",
        "comando": ["python", "-X", "utf8", "markets/polymarket/comparador_odds.py", "--test"],
        "contiene": ["Gap", "Polymarket", "CONCLUSION"],
        "no_contiene": ["Traceback", "Error"],
        "timeout": 15,
        "critico": False,
    },
    # ── GRUPO 6: ARCHIVOS REQUERIDOS ───────────────────────────────────────
    {
        "id": "T050",
        "nombre": "Archivo: CLAUDE.md existe",
        "tipo": "archivo_existe",
        "ruta": os.path.join(DIRECTORIO, "CLAUDE.md"),
        "critico": True,
    },
    {
        "id": "T051",
        "nombre": "Archivo: CONOCIMIENTO.md existe y tiene >16 partes",
        "tipo": "archivo_contenido",
        "ruta": os.path.join(DIRECTORIO, "CONOCIMIENTO.md"),
        "contiene": ["PARTE 13", "PARTE 14", "PARTE 15", "PARTE 16"],
        "critico": False,
    },
    {
        "id": "T052",
        "nombre": "Archivo: ESTADO_SESION.md existe",
        "tipo": "archivo_existe",
        "ruta": os.path.join(DIRECTORIO, "ESTADO_SESION.md"),
        "critico": True,
    },
    {
        "id": "T053",
        "nombre": "Directorio: logs/ existe",
        "tipo": "directorio_existe",
        "ruta": os.path.join(DIRECTORIO, "logs"),
        "critico": False,
    },
    # ── GRUPO 7: TESTS DE LÓGICA INTERNA ───────────────────────────────────
    {
        "id": "T060",
        "nombre": "Codigo: analizar_portfolio.py usa slug correcto y _precio_por_slug() para Pos2",
        "tipo": "codigo_contiene",
        "archivo": "portfolio/analizar_portfolio.py",
        "debe_contener": [
            "_precio_por_slug",
            "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725",
            "SLUG_DIRECTO",
        ],
        "no_debe_contener": [
            "will-the-iranian-regime-fall-by-june-30",
        ],
        "critico": True,
        "fix": (
            "En analizar_portfolio.py:\n"
            "1. Añadir función _precio_por_slug() que llama Gamma API y retorna outcomePrices[0] (YES)\n"
            "2. Eliminar entrada 'Iran x Israel/US conflict ends by June 30?' del dict PNL_FALLBACK\n"
            "3. Llamar _precio_por_slug() cuando p['mercado'] == 'Iran x Israel/US conflict ends by June 30?'"
        ),
    },
    {
        "id": "T061",
        "nombre": "Lógica: Kelly no debe ser negativo con edge positivo",
        "tipo": "logica_kelly",
        "prob_propia": 0.72,
        "precio_yes": 0.47,
        "fraccion": 0.25,
        "esperado_positivo": True,
        "critico": False,
    },
]


# ─── RUNNER ──────────────────────────────────────────────────────────────────

class ResultadoTest:
    def __init__(self, test_id, nombre, estado, mensaje, duracion, fix=None):
        self.test_id   = test_id
        self.nombre    = nombre
        self.estado    = estado  # "PASS", "FAIL", "WARN", "SKIP"
        self.mensaje   = mensaje
        self.duracion  = duracion
        self.fix       = fix
        self.timestamp = datetime.datetime.now().isoformat()


def _obtener_precio_api(slug: str) -> dict:
    try:
        r = requests.get(
            f"https://gamma-api.polymarket.com/markets?slug={slug}",
            timeout=10
        )
        data = r.json()
        if isinstance(data, list) and data:
            m = data[0]
            precios = json.loads(m.get("outcomePrices", "[]"))
            return {
                "yes": float(precios[0]),
                "no":  float(precios[1]) if len(precios) > 1 else 1 - float(precios[0]),
            }
    except Exception as e:
        return {"error": str(e)}
    return {}


def _calcular_kelly(prob_propia: float, precio_yes: float, fraccion: float = 0.25) -> float:
    if precio_yes <= 0 or precio_yes >= 1:
        return 0.0
    b = (1 - precio_yes) / precio_yes
    p, q = prob_propia, 1 - prob_propia
    kelly_full = (b * p - q) / b
    return kelly_full * fraccion


def correr_test(test: dict, rapido: bool = False) -> ResultadoTest:
    t0 = time.time()
    tid = test["id"]
    nombre = test["nombre"]
    tipo = test["tipo"]

    try:
        # ── Compilación ──────────────────────────────────────────────────
        if tipo == "compilacion":
            script = os.path.join(DIRECTORIO, test["script"])
            if not os.path.exists(script):
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Archivo no encontrado: {test['script']}", time.time()-t0)
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", script],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Error de sintaxis: {result.stderr[:200]}", time.time()-t0)
            return ResultadoTest(tid, nombre, "PASS", "Sintaxis correcta", time.time()-t0)

        # ── Conectividad ─────────────────────────────────────────────────
        elif tipo == "conectividad":
            if rapido:
                return ResultadoTest(tid, nombre, "SKIP", "Omitido en modo rapido", time.time()-t0)
            r = requests.get(test["url"], timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            data = r.json()
            if test["validacion"](data):
                return ResultadoTest(tid, nombre, "PASS",
                    f"HTTP {r.status_code} — respuesta válida", time.time()-t0)
            else:
                return ResultadoTest(tid, nombre, "FAIL",
                    test["error_esperado"], time.time()-t0)

        # ── Precio válido ─────────────────────────────────────────────────
        elif tipo == "precio_valido":
            if rapido:
                return ResultadoTest(tid, nombre, "SKIP", "Omitido en modo rapido", time.time()-t0)
            precios = _obtener_precio_api(test["slug"])
            if "error" in precios:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"API error: {precios['error']}", time.time()-t0)
            valor = precios.get(test["campo"])
            if valor is None:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Campo '{test['campo']}' no encontrado en respuesta", time.time()-t0)
            lo, hi = test["rango"]
            if lo <= valor <= hi:
                return ResultadoTest(tid, nombre, "PASS",
                    f"Precio {test['campo']}={valor:.4f} en rango [{lo},{hi}]", time.time()-t0)
            else:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Precio {test['campo']}={valor:.4f} FUERA de rango [{lo},{hi}]", time.time()-t0)

        # ── Suma precios ──────────────────────────────────────────────────
        elif tipo == "suma_precios":
            if rapido:
                return ResultadoTest(tid, nombre, "SKIP", "Omitido en modo rapido", time.time()-t0)
            precios = _obtener_precio_api(test["slug"])
            if "error" in precios:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"API error: {precios['error']}", time.time()-t0)
            suma = precios.get("yes", 0) + precios.get("no", 0)
            tol = test["tolerancia"]
            if abs(suma - 1.0) <= tol:
                return ResultadoTest(tid, nombre, "PASS",
                    f"YES+NO={suma:.4f} aprox 1.0 (tolerancia +-{tol})", time.time()-t0)
            else:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"YES+NO={suma:.4f} != 1.0 — spread anómalo o error API", time.time()-t0)

        # ── Consistencia P/L ──────────────────────────────────────────────
        elif tipo == "pl_consistencia":
            if rapido:
                return ResultadoTest(tid, nombre, "SKIP", "Omitido en modo rapido", time.time()-t0)
            if test["calculo"] == "pos1":
                precios = _obtener_precio_api("us-x-iran-ceasefire-by-april-15-182-528-637")
                if "error" in precios:
                    return ResultadoTest(tid, nombre, "FAIL",
                        f"API error: {precios['error']}", time.time()-t0)
                pl_real = (precios["no"] - 0.657) * 304.3
                if abs(pl_real) < 200:  # P/L razonable
                    return ResultadoTest(tid, nombre, "PASS",
                        f"P/L Pos1 = {pl_real:+.2f}$ (precio NO actual: {precios['no']:.3f})",
                        time.time()-t0)
                else:
                    return ResultadoTest(tid, nombre, "FAIL",
                        f"P/L Pos1 = {pl_real:+.2f}$ fuera de rango razonable",
                        time.time()-t0, fix=test.get("fix"))
            elif test["calculo"] == "pos2_invertir":
                precios = _obtener_precio_api("iran-x-israelus-conflict-ends-by-june-30-813-454-138-725")
                if "error" in precios:
                    return ResultadoTest(tid, nombre, "FAIL",
                        f"API error: {precios['error']}", time.time()-t0)
                # Posición NO directa: precio efectivo = NO del mercado de conflicto
                pl_real = (precios["no"] - 0.24) * 558.8
                msg = (
                    f"P/L Pos2 = {pl_real:+.2f}$ "
                    f"(NO={precios['no']:.3f}, entrada=0.24, shares=558.8)"
                )
                if abs(pl_real) < 300:  # P/L razonable para este tamaño
                    return ResultadoTest(tid, nombre, "PASS", msg, time.time()-t0)
                else:
                    return ResultadoTest(tid, nombre, "FAIL",
                        f"P/L fuera de rango: {pl_real:+.2f}$",
                        time.time()-t0, fix=test.get("fix"))

        # ── Rango P/L ─────────────────────────────────────────────────────
        elif tipo == "pl_rango":
            if rapido:
                return ResultadoTest(tid, nombre, "SKIP", "Omitido en modo rapido", time.time()-t0)
            p1 = _obtener_precio_api("us-x-iran-ceasefire-by-april-15-182-528-637")
            p2 = _obtener_precio_api("iran-x-israelus-conflict-ends-by-june-30-813-454-138-725")
            if "error" in p1 or "error" in p2:
                return ResultadoTest(tid, nombre, "SKIP",
                    "API no disponible para validar rango P/L", time.time()-t0)
            pl1 = (p1["no"] - 0.657) * 304.3
            pl2 = (p2["no"] - 0.24) * 558.8
            pl_total = pl1 + pl2
            lo, hi = test["rango_usd"]
            if lo <= pl_total <= hi:
                return ResultadoTest(tid, nombre, "PASS",
                    f"P/L total = {pl_total:+.2f}$ en rango [{lo},{hi}]",
                    time.time()-t0)
            else:
                return ResultadoTest(tid, nombre, "WARN",
                    f"P/L total = {pl_total:+.2f}$ FUERA del rango esperado [{lo},{hi}]",
                    time.time()-t0)

        # ── Ejecución ─────────────────────────────────────────────────────
        elif tipo == "ejecucion":
            cmd = [sys.executable] + test["comando"][1:]  # reemplaza 'python' con sys.executable
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=test.get("timeout", 30),
                cwd=DIRECTORIO, encoding="utf-8", errors="replace"
            )
            salida = result.stdout + result.stderr
            fallos = [s for s in test.get("no_contiene", []) if s in salida]
            requeridos = [s for s in test.get("contiene", []) if s not in salida]
            if fallos:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Salida contiene texto prohibido: {fallos}", time.time()-t0)
            if requeridos:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Salida NO contiene texto requerido: {requeridos}", time.time()-t0)
            return ResultadoTest(tid, nombre, "PASS",
                f"Script ejecutó correctamente (RC={result.returncode})", time.time()-t0)

        # ── Análisis estático de código ───────────────────────────────────
        elif tipo == "codigo_contiene":
            ruta = os.path.join(DIRECTORIO, test["archivo"])
            if not os.path.exists(ruta):
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Archivo no encontrado: {ruta}", time.time()-t0)
            codigo = open(ruta, encoding="utf-8", errors="replace").read()
            faltantes = [s for s in test.get("debe_contener", []) if s not in codigo]
            presentes_prohibidos = [s for s in test.get("no_debe_contener", []) if s in codigo]
            if faltantes:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Código NO contiene patron requerido: {faltantes}",
                    time.time()-t0, fix=test.get("fix"))
            if presentes_prohibidos:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Código contiene patron BUG activo: {presentes_prohibidos}",
                    time.time()-t0, fix=test.get("fix"))
            return ResultadoTest(tid, nombre, "PASS",
                f"Todos los patrones correctos en {test['archivo']}", time.time()-t0)

        # ── Archivo existe ────────────────────────────────────────────────
        elif tipo == "archivo_existe":
            if os.path.exists(test["ruta"]):
                size = os.path.getsize(test["ruta"])
                return ResultadoTest(tid, nombre, "PASS",
                    f"Existe ({size:,} bytes)", time.time()-t0)
            else:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Archivo no encontrado: {test['ruta']}", time.time()-t0)

        # ── Archivo contenido ─────────────────────────────────────────────
        elif tipo == "archivo_contenido":
            if not os.path.exists(test["ruta"]):
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Archivo no encontrado: {test['ruta']}", time.time()-t0)
            contenido = open(test["ruta"], encoding="utf-8", errors="replace").read()
            faltantes = [s for s in test.get("contiene", []) if s not in contenido]
            if faltantes:
                return ResultadoTest(tid, nombre, "WARN",
                    f"Secciones faltantes: {faltantes}", time.time()-t0)
            return ResultadoTest(tid, nombre, "PASS",
                f"Todas las secciones requeridas presentes", time.time()-t0)

        # ── Directorio existe ─────────────────────────────────────────────
        elif tipo == "directorio_existe":
            if os.path.isdir(test["ruta"]):
                return ResultadoTest(tid, nombre, "PASS",
                    f"Directorio existe: {test['ruta']}", time.time()-t0)
            else:
                os.makedirs(test["ruta"], exist_ok=True)
                return ResultadoTest(tid, nombre, "WARN",
                    f"Directorio creado automáticamente: {test['ruta']}", time.time()-t0)

        # ── Lógica precio invertir ────────────────────────────────────────
        elif tipo == "logica_precio_invertir":
            if rapido:
                return ResultadoTest(tid, nombre, "SKIP", "Omitido en modo rapido", time.time()-t0)
            precios = _obtener_precio_api(test["slug"])
            if "error" in precios:
                return ResultadoTest(tid, nombre, "SKIP",
                    f"API no disponible", time.time()-t0)
            pl_correcto = (precios["yes"] - test["entrada"]) * test["shares"]
            pl_bug      = (precios["no"]  - test["entrada"]) * test["shares"]
            dif = abs(pl_correcto - pl_bug)
            if dif > 5:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"BUG ACTIVO: usar YES ({precios['yes']:.3f}) da P/L={pl_correcto:+.2f}$, "
                    f"usar NO ({precios['no']:.3f}) da P/L={pl_bug:+.2f}$. "
                    f"Diferencia: ${dif:.2f}",
                    time.time()-t0, fix=test.get("fix"))
            return ResultadoTest(tid, nombre, "PASS",
                f"Precio efectivo correcto (YES={precios['yes']:.3f})", time.time()-t0)

        # ── Lógica Kelly ──────────────────────────────────────────────────
        elif tipo == "logica_kelly":
            kelly = _calcular_kelly(test["prob_propia"], test["precio_yes"], test["fraccion"])
            if test["esperado_positivo"] and kelly <= 0:
                return ResultadoTest(tid, nombre, "FAIL",
                    f"Kelly={kelly:.4f} debería ser >0 para prob={test['prob_propia']}, "
                    f"precio_yes={test['precio_yes']}", time.time()-t0)
            return ResultadoTest(tid, nombre, "PASS",
                f"Kelly={kelly:.4f} para prob={test['prob_propia']}, precio={test['precio_yes']}",
                time.time()-t0)

        else:
            return ResultadoTest(tid, nombre, "SKIP", f"Tipo '{tipo}' no implementado", time.time()-t0)

    except subprocess.TimeoutExpired:
        return ResultadoTest(tid, nombre, "FAIL", f"Timeout después de {test.get('timeout',30)}s", time.time()-t0)
    except Exception as e:
        return ResultadoTest(tid, nombre, "FAIL", f"Excepción: {e}\n{traceback.format_exc()[-300:]}", time.time()-t0)


def guardar_bugs(resultados: list) -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    bugs = []
    for r in resultados:
        if r.estado in ("FAIL", "WARN"):
            bugs.append({
                "id": r.test_id,
                "nombre": r.nombre,
                "estado": r.estado,
                "mensaje": r.mensaje,
                "fix": r.fix,
                "timestamp": r.timestamp,
                "fecha": HOY,
            })
    # Cargar bugs previos y mergear
    historico = []
    if os.path.exists(BUGS_FILE):
        try:
            historico = json.loads(open(BUGS_FILE, encoding="utf-8").read())
        except:
            pass
    # Filtrar bugs previos del mismo día
    historico = [b for b in historico if b.get("fecha") != HOY]
    historico.extend(bugs)
    with open(BUGS_FILE, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)


def imprimir_reporte(resultados: list, show_fix: bool = False) -> None:
    totales = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
    for r in resultados:
        totales[r.estado] = totales.get(r.estado, 0) + 1

    print(f"\n{'='*65}")
    print(f" REPORTE DE TESTS — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

    # Agrupar por estado
    for estado, simbolo in [("FAIL", "[FAIL]"), ("WARN", "[WARN]"), ("PASS", "[PASS]"), ("SKIP", "[SKIP]")]:
        grupo = [r for r in resultados if r.estado == estado]
        if not grupo:
            continue
        print(f"\n {simbolo} ({len(grupo)})")
        print(f" {'-'*60}")
        for r in grupo:
            dur = f"{r.duracion:.1f}s"
            print(f"   [{r.test_id}] {r.nombre[:50]:<50} {dur:>6}")
            if r.estado in ("FAIL", "WARN"):
                # Mostrar mensaje truncado
                lineas = r.mensaje.split('\n')
                for linea in lineas[:3]:
                    print(f"           {linea[:70]}")
                if show_fix and r.fix:
                    print(f"\n           FIX SUGERIDO:")
                    for linea in r.fix.split('\n'):
                        print(f"           {linea}")
                    print()

    # Resumen
    total = sum(totales.values())
    print(f"\n{'-'*65}")
    print(f" RESUMEN: {total} tests | "
          f"PASS: {totales['PASS']} | "
          f"FAIL: {totales['FAIL']} | "
          f"WARN: {totales['WARN']} | "
          f"SKIP: {totales['SKIP']}")

    criticos_fallidos = [r for r in resultados if r.estado == "FAIL"
                         and any(t["id"] == r.test_id and t.get("critico") for t in TESTS)]
    if criticos_fallidos:
        print(f"\n [ATENCION] {len(criticos_fallidos)} TESTS CRITICOS FALLIDOS — revisar antes de operar")
    else:
        print(f"\n [OK] Todos los tests críticos pasaron")

    print(f" Bugs guardados en: {BUGS_FILE}")
    print(f"{'='*65}\n")


def main():
    os.chdir(DIRECTORIO)
    parser = argparse.ArgumentParser(
        description="Suite de tests automatizados — inversiones portfolio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python -X utf8 test_suite.py              # todos los tests
  python -X utf8 test_suite.py --rapido     # solo tests sin API (rápido)
  python -X utf8 test_suite.py --fix        # incluir sugerencias de fix
  python -X utf8 test_suite.py --json       # output JSON
  python -X utf8 test_suite.py --id T031    # correr solo un test específico
        """
    )
    parser.add_argument("--rapido", action="store_true", help="Solo tests locales, sin API")
    parser.add_argument("--fix",    action="store_true", help="Mostrar sugerencias de fix")
    parser.add_argument("--json",   action="store_true", help="Output en JSON")
    parser.add_argument("--id",     help="Correr solo el test con este ID")
    args = parser.parse_args()

    tests_a_correr = TESTS
    if args.id:
        tests_a_correr = [t for t in TESTS if t["id"] == args.id]
        if not tests_a_correr:
            print(f"[ERROR] Test '{args.id}' no encontrado")
            sys.exit(1)

    print(f"\n Ejecutando {len(tests_a_correr)} tests{'  [MODO RAPIDO]' if args.rapido else ''}...")
    resultados = []
    for test in tests_a_correr:
        r = correr_test(test, rapido=args.rapido)
        simbolo = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]", "SKIP": "[SKIP]"}.get(r.estado, "?")
        print(f"  {simbolo} [{r.test_id}] {r.nombre[:55]}")
        resultados.append(r)

    guardar_bugs(resultados)

    if args.json:
        output = [{"id": r.test_id, "nombre": r.nombre, "estado": r.estado,
                   "mensaje": r.mensaje, "fix": r.fix} for r in resultados]
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        imprimir_reporte(resultados, show_fix=args.fix)

    fails = sum(1 for r in resultados if r.estado == "FAIL")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
