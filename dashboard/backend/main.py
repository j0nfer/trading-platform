"""
dashboard/backend/main.py — API FastAPI para trading-platform

Endpoints:
  GET /                    → health check
  GET /portfolio           → posiciones + P/L en tiempo real
  GET /prices              → precios actuales de ambos mercados
  GET /whales              → actividad whale últimas N horas
  GET /signals             → señales activas (TACO, escalada, whale)
  GET /portfolio/summary   → resumen ejecutivo compacto

Arrancar:
  uvicorn dashboard.backend.main:app --reload --port 8000
"""

import sys
import os
import json
import datetime
import glob as _glob
import asyncio
import subprocess
from contextlib import asynccontextmanager

import aiosqlite

TRADING_DIR = os.environ.get("TRADING_DIR", "C:\\inversiones")
NEWS_DB     = os.path.join(TRADING_DIR, "news_cache.db")
sys.path.insert(0, TRADING_DIR)

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ─── DB SCHEMA ───────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS news (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    url         TEXT,
    source      TEXT,
    market      TEXT,
    priority    TEXT    DEFAULT 'MEDIA',
    summary     TEXT,
    published_at TEXT,
    fetched_at  TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_news_fetched  ON news(fetched_at);
CREATE INDEX IF NOT EXISTS idx_news_market   ON news(market);
CREATE INDEX IF NOT EXISTS idx_news_priority ON news(priority);
"""


async def _init_db():
    async with aiosqlite.connect(NEWS_DB) as db:
        await db.executescript(_DDL)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_db()
    yield

# Importar core.py directamente (evita conflicto con paquete core/)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_core", os.path.join(TRADING_DIR, "core.py"))
_core = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_core)
fetch_precio              = _core.fetch_precio
fetch_trades              = _core.fetch_trades
cargar_portfolio          = _core.cargar_portfolio
calcular_pnl              = _core.calcular_pnl
dias_restantes            = _core.dias_restantes
SLUG_CEASEFIRE_APR15      = _core.SLUG_CEASEFIRE_APR15
SLUG_CONFLICT_JUN30       = _core.SLUG_CONFLICT_JUN30
CONDITION_CEASEFIRE_APR15 = _core.CONDITION_CEASEFIRE_APR15
CONDITION_CONFLICT_JUN30  = _core.CONDITION_CONFLICT_JUN30
GAMMA_API                 = _core.GAMMA_API

# ─── APP ─────────────────────────────────────────────────────────────────────

DESCRIPTION = """
## Trading Platform API 🎯

API en tiempo real para gestión de portfolio en **Polymarket** — especializada en mercados geopolíticos.

---

### 📊 Posiciones actuales
| # | Mercado | Dir | Entrada |
|---|---------|-----|---------|
| 1 | US x Iran ceasefire by April 15? | **NO** | 65.7¢ |
| 2 | Iran x Israel/US conflict ends by June 30? | **NO** | 24¢ |

---

### 🔌 Endpoints disponibles

| Endpoint | Descripción |
|----------|-------------|
| `GET /` | Health check |
| `GET /prices` | Precios YES/NO en tiempo real |
| `GET /portfolio` | Posiciones con P/L calculado |
| `GET /portfolio/summary` | Resumen ejecutivo compacto |
| `GET /whales` | Actividad grandes jugadores |
| `GET /signals` | Señales activas de trading |

---

### ⚡ APIs externas
- **Polymarket Gamma API** → precios de mercados
- **Polymarket Data API** → actividad de trades
- **Yahoo Finance** → precio Brent en tiempo real

---

### 📅 Deadlines críticos
- **6 abril** — Trump decide si reanuda strikes sobre Irán
- **15 abril** — Resolución Ceasefire Apr15
- **30 junio** — Resolución Conflict Jun30
"""

TAGS = [
    {
        "name": "sistema",
        "description": "Health check y estado del sistema",
    },
    {
        "name": "precios",
        "description": "Precios en tiempo real de mercados Polymarket",
    },
    {
        "name": "portfolio",
        "description": "Posiciones abiertas, P/L y resumen ejecutivo",
    },
    {
        "name": "inteligencia",
        "description": "Actividad whale y señales de trading accionables",
    },
    {
        "name": "noticias",
        "description": "Noticias y eventos relevantes desde news_cache.db",
    },
]

app = FastAPI(
    title="Trading Platform API",
    description=DESCRIPTION,
    version="1.0.0",
    openapi_tags=TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "Jon — Trading Platform",
        "url": "https://github.com/j0nfer/trading-platform",
    },
    license_info={
        "name": "Private",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── HELPERS INTERNOS ─────────────────────────────────────────────────────────

def _get_precios_posiciones() -> dict:
    """Obtiene precios actuales de ambas posiciones."""
    p1 = fetch_precio(SLUG_CEASEFIRE_APR15)
    p2 = fetch_precio(SLUG_CONFLICT_JUN30)
    return {"ceasefire_apr15": p1, "conflict_jun30": p2}


def _build_posicion(pos: dict, precio_no: float, fuente: str) -> dict:
    """Construye dict de posición con P/L calculado."""
    entrada   = pos["precio_entrada_avg"]
    shares    = pos["shares"]
    pnl_abs   = calcular_pnl(precio_no, entrada, shares)
    pnl_pct   = ((precio_no - entrada) / entrada) * 100
    dias      = dias_restantes(pos["fecha_resolucion"])
    costo     = entrada * shares
    valor     = precio_no * shares

    return {
        "id":             pos["id"],
        "mercado":        pos["mercado"],
        "slug":           pos.get("slug", ""),
        "direccion":      pos["direccion"],
        "entrada":        entrada,
        "precio_actual":  round(precio_no, 4),
        "shares":         shares,
        "costo":          round(costo, 2),
        "valor":          round(valor, 2),
        "pnl_absoluto":   round(pnl_abs, 2),
        "pnl_pct":        round(pnl_pct, 2),
        "dias_restantes": dias,
        "fecha_resolucion": pos["fecha_resolucion"],
        "fuente_precio":  fuente,
    }


def _analizar_whales(trades: list, nuestra_pos: str, horas: int, umbral: float) -> dict:
    """Analiza actividad whale en lista de trades."""
    corte = datetime.datetime.now() - datetime.timedelta(hours=horas)
    whales = []
    vol_favor = vol_contra = 0.0

    for t in trades:
        dt = datetime.datetime.fromtimestamp(t["timestamp"])
        if dt < corte:
            continue
        size = float(t.get("size", 0))
        if size < umbral:
            continue

        outcome = t["outcome"].upper()
        side    = t["side"].upper()
        n       = nuestra_pos.upper()

        a_favor = (
            (outcome == n and side == "BUY") or
            (outcome != n and side == "SELL")
        )

        if a_favor:
            vol_favor += size
        else:
            vol_contra += size

        whales.append({
            "wallet":  t.get("name") or t["proxyWallet"][:16],
            "size":    round(size, 2),
            "outcome": t["outcome"],
            "side":    t["side"],
            "precio":  round(float(t.get("price", 0)), 3),
            "hora":    dt.strftime("%H:%M"),
            "a_favor": a_favor,
        })

    total = vol_favor + vol_contra
    ratio = (vol_favor / total) if total > 0 else 0.5

    if ratio >= 0.75:
        señal = "FUERTE_FAVOR"
    elif ratio >= 0.55:
        señal = "MODERADO_FAVOR"
    elif ratio >= 0.45:
        señal = "NEUTRAL"
    elif ratio >= 0.25:
        señal = "MODERADO_CONTRA"
    else:
        señal = "FUERTE_CONTRA"

    return {
        "whales":       sorted(whales, key=lambda x: x["size"], reverse=True)[:10],
        "vol_favor":    round(vol_favor, 2),
        "vol_contra":   round(vol_contra, 2),
        "señal":        señal,
        "n_whales":     len(whales),
    }


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@app.get("/", tags=["sistema"])
def health_check():
    """Health check — confirma que la API está operativa."""
    return {
        "status":    "ok",
        "timestamp": datetime.datetime.now().isoformat(),
        "version":   "1.0.0",
    }


@app.get("/prices", tags=["precios"])
def get_prices():
    """Precios actuales YES/NO de ambos mercados en tiempo real."""
    precios = _get_precios_posiciones()
    resultado = {}

    for nombre, p in precios.items():
        if "error" in p:
            resultado[nombre] = {"error": p["error"]}
        else:
            resultado[nombre] = {
                "yes":     round(p["yes"], 4),
                "no":      round(p["no"],  4),
                "vol":     round(p["vol"], 0),
                "titulo":  p["titulo"],
                "end_date": p["end_date"],
            }

    resultado["timestamp"] = datetime.datetime.now().isoformat()
    return resultado


@app.get("/portfolio", tags=["portfolio"])
def get_portfolio():
    """
    Posiciones abiertas con P/L calculado en tiempo real.
    Incluye precios live de Polymarket.
    """
    try:
        data      = cargar_portfolio()
        posiciones_raw = data.get("posiciones_polymarket", [])
        precios   = _get_precios_posiciones()
    except Exception as e:
        return {"error": str(e)}

    slugs_map = {
        SLUG_CEASEFIRE_APR15: ("ceasefire_apr15", precios["ceasefire_apr15"]),
        SLUG_CONFLICT_JUN30:  ("conflict_jun30",  precios["conflict_jun30"]),
    }

    posiciones  = []
    total_costo = total_valor = total_pnl = 0.0

    for pos in posiciones_raw:
        slug = pos.get("slug", "")
        if slug in slugs_map:
            _, precio_data = slugs_map[slug]
            if "error" in precio_data:
                precio_no = pos["precio_entrada_avg"]
                fuente    = "estimado"
            else:
                precio_no = precio_data["no"]
                fuente    = "live"
        else:
            precio_no = pos["precio_entrada_avg"]
            fuente    = "estimado"

        p = _build_posicion(pos, precio_no, fuente)
        total_costo += p["costo"]
        total_valor += p["valor"]
        total_pnl   += p["pnl_absoluto"]
        posiciones.append(p)

    return {
        "posiciones":    posiciones,
        "resumen": {
            "total_costo":  round(total_costo, 2),
            "total_valor":  round(total_valor, 2),
            "total_pnl":    round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / total_costo * 100) if total_costo else 0, 2),
            "cash":         data.get("perfil", {}).get("cash_disponible", 0),
            "capital_total": data.get("perfil", {}).get("capital_total_usdc", 0),
        },
        "timestamp": datetime.datetime.now().isoformat(),
    }


@app.get("/portfolio/summary", tags=["portfolio"])
def get_portfolio_summary():
    """Resumen ejecutivo compacto — ideal para dashboard header."""
    try:
        p1 = fetch_precio(SLUG_CEASEFIRE_APR15)
        p2 = fetch_precio(SLUG_CONFLICT_JUN30)

        pnl1 = calcular_pnl(p1["no"], 0.657, 304.3) if "error" not in p1 else 0
        pnl2 = calcular_pnl(p2["no"], 0.240, 558.8) if "error" not in p2 else 0

        return {
            "total_pnl":    round(pnl1 + pnl2, 2),
            "pos1_pnl":     round(pnl1, 2),
            "pos2_pnl":     round(pnl2, 2),
            "pos1_no":      round(p1.get("no", 0), 4),
            "pos2_no":      round(p2.get("no", 0), 4),
            "dias_pos1":    dias_restantes("2026-04-15"),
            "dias_pos2":    dias_restantes("2026-06-30"),
            "timestamp":    datetime.datetime.now().isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/whales", tags=["inteligencia"])
def get_whales(
    horas:  int   = Query(default=6,   ge=1, le=168, description="Ventana temporal en horas"),
    umbral: float = Query(default=500, ge=0,          description="Tamaño mínimo de trade en $"),
):
    """
    Actividad whale en ambas posiciones.
    Detecta trades grandes y calcula si van a favor o en contra.
    """
    resultado = {}

    mercados = [
        ("ceasefire_apr15", CONDITION_CEASEFIRE_APR15, "NO"),
        ("conflict_jun30",  CONDITION_CONFLICT_JUN30,  "NO"),
    ]

    for nombre, cid, nuestra_pos in mercados:
        trades = fetch_trades(cid, limite=300)
        analisis = _analizar_whales(trades, nuestra_pos, horas, umbral)
        resultado[nombre] = analisis

    resultado["parametros"] = {"horas": horas, "umbral": umbral}
    resultado["timestamp"]  = datetime.datetime.now().isoformat()
    return resultado


@app.get("/signals", tags=["inteligencia"])
def get_signals():
    """
    Señales activas: TACO, escalada, whale, precio.
    Consolida toda la información relevante para tomar decisiones.
    """
    señales = []

    # ── Señal de precio Pos1 ──────────────────────────────────────────────
    p1 = fetch_precio(SLUG_CEASEFIRE_APR15)
    if "error" not in p1:
        no = p1["no"]
        if no >= 0.90:
            señales.append({
                "tipo":     "PRECIO_ALTO",
                "mercado":  "Ceasefire Apr15",
                "mensaje":  f"NO en {no:.1%} — considerar venta parcial (upside restante < 10¢)",
                "urgencia": "ALTA",
                "accion":   "EVALUAR_VENTA",
            })
        elif no <= 0.75:
            señales.append({
                "tipo":     "PRECIO_BAJO",
                "mercado":  "Ceasefire Apr15",
                "mensaje":  f"NO cayó a {no:.1%} — posible señal de ceasefire",
                "urgencia": "CRITICA",
                "accion":   "VENDER_INMEDIATO",
            })

    # ── Señal de precio Pos2 ──────────────────────────────────────────────
    p2 = fetch_precio(SLUG_CONFLICT_JUN30)
    if "error" not in p2:
        no = p2["no"]
        if no <= 0.25:
            señales.append({
                "tipo":     "OPORTUNIDAD",
                "mercado":  "Conflict Jun30",
                "mensaje":  f"NO bajó a {no:.1%} — oportunidad de reforzar posición",
                "urgencia": "MEDIA",
                "accion":   "CONSIDERAR_COMPRA",
            })

    # ── Señal whale Pos1 ──────────────────────────────────────────────────
    trades1 = fetch_trades(CONDITION_CEASEFIRE_APR15, limite=100)
    whale1  = _analizar_whales(trades1, "NO", 2, 3000)
    if whale1["señal"] in ("FUERTE_CONTRA", "MODERADO_CONTRA"):
        señales.append({
            "tipo":     "WHALE_CONTRA",
            "mercado":  "Ceasefire Apr15",
            "mensaje":  f"Whales apostando en contra — ${whale1['vol_contra']:,.0f} últimas 2h",
            "urgencia": "ALTA",
            "accion":   "MONITORIZAR",
        })

    # ── Deadline ─────────────────────────────────────────────────────────
    dias1 = dias_restantes("2026-04-15")
    if dias1 <= 3:
        señales.append({
            "tipo":     "DEADLINE",
            "mercado":  "Ceasefire Apr15",
            "mensaje":  f"Resolución en {dias1} días — preparar estrategia de salida",
            "urgencia": "ALTA",
            "accion":   "PREPARAR_SALIDA",
        })

    return {
        "señales":    señales,
        "n_señales":  len(señales),
        "timestamp":  datetime.datetime.now().isoformat(),
    }


@app.get("/history", tags=["portfolio"])
def get_history(dias: int = Query(default=14, ge=1, le=90, description="Días de histórico")):
    """
    Histórico de P/L diario construido desde los logs de sesión.
    Combina snapshots guardados + precio en tiempo real de hoy.
    """
    puntos = []

    # ── Leer snapshots de logs diarios ──────────────────────────────────────
    logs_dir = os.path.join(TRADING_DIR, "logs")
    pattern  = os.path.join(logs_dir, "snapshot_*.json")
    archivos = sorted(_glob.glob(pattern))[-dias:]

    for path in archivos:
        try:
            with open(path, encoding="utf-8") as f:
                snap = json.load(f)
            puntos.append({
                "fecha":    snap["fecha"],
                "pnl":      round(snap.get("pnl_total", 0), 2),
                "pnl_pos1": round(snap.get("pnl_pos1", 0), 2),
                "pnl_pos2": round(snap.get("pnl_pos2", 0), 2),
                "no_pos1":  round(snap.get("no_pos1", 0), 4),
                "no_pos2":  round(snap.get("no_pos2", 0), 4),
            })
        except Exception:
            continue

    # ── Añadir punto de hoy con precio live ─────────────────────────────────
    try:
        p1 = fetch_precio(SLUG_CEASEFIRE_APR15)
        p2 = fetch_precio(SLUG_CONFLICT_JUN30)
        if "error" not in p1 and "error" not in p2:
            pnl1 = calcular_pnl(p1["no"], 0.657, 304.3)
            pnl2 = calcular_pnl(p2["no"], 0.240, 558.8)
            hoy  = datetime.date.today().isoformat()
            # Evitar duplicado si ya hay snapshot de hoy
            if not puntos or puntos[-1]["fecha"] != hoy:
                puntos.append({
                    "fecha":    hoy,
                    "pnl":      round(pnl1 + pnl2, 2),
                    "pnl_pos1": round(pnl1, 2),
                    "pnl_pos2": round(pnl2, 2),
                    "no_pos1":  round(p1["no"], 4),
                    "no_pos2":  round(p2["no"], 4),
                    "live":     True,
                })
    except Exception:
        pass

    # ── Si no hay logs, generar serie sintética desde CLAUDE.md ─────────────
    # Fechas clave conocidas: inicio posiciones ~28 feb 2026
    if len(puntos) < 2:
        SEED = [
            ("2026-03-01", -15, 0.68, 0.22),
            ("2026-03-08",  -8, 0.72, 0.20),
            ("2026-03-15",  12, 0.78, 0.22),
            ("2026-03-22",  35, 0.82, 0.25),
            ("2026-03-28",  26, 0.86, 0.14),
            ("2026-04-01",  95, 0.91, 0.33),
            ("2026-04-03", 177, 0.935, 0.405),
        ]
        puntos = [
            {
                "fecha":    f,
                "pnl":      p,
                "pnl_pos1": round((n1 - 0.657) * 304.3, 2),
                "pnl_pos2": round((n2 - 0.240) * 558.8, 2),
                "no_pos1":  n1,
                "no_pos2":  n2,
                "seed":     True,
            }
            for f, p, n1, n2 in SEED
        ]

    return {
        "puntos":    puntos,
        "n_puntos":  len(puntos),
        "timestamp": datetime.datetime.now().isoformat(),
    }


# ─── NOTICIAS ────────────────────────────────────────────────────────────────

@app.get("/news", tags=["noticias"])
async def get_news(
    market:   str | None = Query(default=None,  description="Filtrar por mercado (ej: 'iran', 'wti')"),
    priority: str | None = Query(default=None,  description="CRITICA | ALTA | MEDIA | BAJA"),
    hours:    int        = Query(default=24, ge=1, le=720, description="Ventana temporal en horas"),
    limit:    int        = Query(default=50, ge=1, le=200, description="Máximo de resultados"),
):
    """
    Noticias almacenadas en news_cache.db.
    Filtrables por mercado, prioridad y ventana temporal.
    """
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat()

    conditions = ["fetched_at >= ?"]
    params: list = [cutoff]

    if market:
        conditions.append("LOWER(market) LIKE ?")
        params.append(f"%{market.lower()}%")
    if priority:
        conditions.append("UPPER(priority) = ?")
        params.append(priority.upper())

    where = " AND ".join(conditions)
    sql   = f"SELECT * FROM news WHERE {where} ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)

    try:
        async with aiosqlite.connect(NEWS_DB) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
        items = [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "items":     items,
        "n_items":   len(items),
        "filtros":   {"market": market, "priority": priority, "hours": hours},
        "timestamp": datetime.datetime.now().isoformat(),
    }


@app.get("/news/stats", tags=["noticias"])
async def get_news_stats(
    hours: int = Query(default=24, ge=1, le=720, description="Ventana temporal en horas"),
):
    """Cuenta de noticias por prioridad en la ventana temporal indicada."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat()

    sql = """
        SELECT priority, COUNT(*) as total
        FROM news
        WHERE fetched_at >= ?
        GROUP BY priority
        ORDER BY CASE priority
            WHEN 'CRITICA' THEN 1
            WHEN 'ALTA'    THEN 2
            WHEN 'MEDIA'   THEN 3
            WHEN 'BAJA'    THEN 4
            ELSE 5 END
    """

    try:
        async with aiosqlite.connect(NEWS_DB) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, [cutoff]) as cur:
                rows = await cur.fetchall()

            async with db.execute(
                "SELECT COUNT(*) FROM news WHERE fetched_at >= ?", [cutoff]
            ) as cur2:
                total = (await cur2.fetchone())[0]

            async with db.execute(
                "SELECT MAX(fetched_at) FROM news"
            ) as cur3:
                ultima = (await cur3.fetchone())[0]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    por_prioridad = {r["priority"]: r["total"] for r in rows}

    return {
        "total":          total,
        "por_prioridad":  por_prioridad,
        "criticas":       por_prioridad.get("CRITICA", 0),
        "altas":          por_prioridad.get("ALTA",    0),
        "medias":         por_prioridad.get("MEDIA",   0),
        "bajas":          por_prioridad.get("BAJA",    0),
        "ultima_noticia": ultima,
        "ventana_horas":  hours,
        "timestamp":      datetime.datetime.now().isoformat(),
    }


@app.post("/news/refresh", tags=["noticias"])
async def refresh_news():
    """
    Ejecuta un ciclo de news_monitor.py para actualizar la DB.
    Devuelve stdout/stderr y código de salida.
    """
    monitor_path = os.path.join(TRADING_DIR, "news_monitor.py")

    if not os.path.exists(monitor_path):
        raise HTTPException(
            status_code=404,
            detail=f"news_monitor.py no encontrado en {TRADING_DIR}",
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-X", "utf8", monitor_path, "--once",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=TRADING_DIR,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="news_monitor.py tardó más de 60s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "exit_code": proc.returncode,
        "ok":        proc.returncode == 0,
        "stdout":    stdout.decode("utf-8", errors="replace")[-2000:],
        "stderr":    stderr.decode("utf-8", errors="replace")[-500:],
        "timestamp": datetime.datetime.now().isoformat(),
    }
