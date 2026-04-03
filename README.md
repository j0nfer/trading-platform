# Trading Platform — Jon

[![CI — Tests](https://github.com/j0nfer/trading-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/j0nfer/trading-platform/actions/workflows/ci.yml)

**Directorio:** `C:\inversiones\`
**Actualizado:** 2026-04-03

---

## Archivos del sistema

| Archivo | Descripcion |
|---|---|
| `CLAUDE.md` | Perfil completo del inversor, protocolo de fuentes y reglas de analisis |
| `portfolio.json` | Posiciones actuales, watchlist y contexto macro (editar cuando cambien posiciones) |
| `analizar_portfolio.py` | Resumen completo: posiciones, alertas de riesgo, noticias Iran via RSS |
| `buscar_edge.py` | Buscador de oportunidades en Polymarket con protocolo 6 pasos |
| `monitor_precios.py` | Precios SNDK + WTI/Brent con señales de entrada |
| `alertas.py` | Monitor automatico por hora — escribe en `alertas.log` |
| `alertas.log` | Log de alertas criticas (generado automaticamente) |

---

## Como ejecutar desde PowerShell

Abrir PowerShell y navegar al directorio:
```
cd C:\inversiones
```

### Resumen diario (ejecutar cada manana)
```
python analizar_portfolio.py
```

### Monitorear precios SNDK + petroleo
```
python monitor_precios.py
```

### Buscar oportunidades en Polymarket
```
python buscar_edge.py
```

### Monitor de alertas — una sola ejecucion
```
python alertas.py
```

### Monitor de alertas — loop continuo cada hora (dejar corriendo)
```
python alertas.py --loop
```

### Probar que alertas.py funciona y escribe en el log
```
python alertas.py --test
```

### Ver el log de alertas
```
Get-Content alertas.log -Tail 50
```

### Seguir el log en tiempo real
```
Get-Content alertas.log -Wait
```

---

## Como actualizar posiciones

Editar `portfolio.json` directamente cuando:
- Cambie el precio de entrada de una posicion
- Se añada o cierre una posicion
- Cambie el contexto macro (precios petroleo, eventos criticos)

Campos clave a actualizar:
```json
"valor_actual": 235.84,
"pnl_absoluto": 35.84,
"pnl_pct": 17.9,
"condition_id": null  <- pegar aqui el ID de Polymarket para precios live
```

---

## Como obtener precios en vivo de Polymarket

1. Abrir el mercado en polymarket.com
2. Pulsar F12 (DevTools) -> pestana Network
3. Recargar pagina y filtrar por `clob.polymarket.com`
4. Buscar peticion a `/markets/0x...` — ese hash es el `condition_id`
5. Pegarlo en `portfolio.json` en el campo `condition_id` de la posicion

---

## Protocolo de fuentes — recordatorio

| Nivel | Descripcion | Ejemplos |
|---|---|---|
| A | Fuentes primarias oficiales — maxima confianza | Fed, IEA, ONU, IAEA, FRED |
| B | Medios verificables — usar con criterio | Reuters, AP, Al Jazeera, BBC |
| C | Conflicto de interes — marcar siempre | Goldman Sachs, Bloomberg, CNN |

Nunca citar Nivel C sin indicar `[FUENTE C — conflicto de interes]`

---

## Eventos criticos proximos

| Fecha | Evento |
|---|---|
| 6 abril 2026 | Trump decide si reanuda strikes sobre infraestructura energetica Iran |
| 15 abril 2026 | Resolucion mercado "Iran ceasefire April 15" |
| 29 abril 2026 | Reunion Fed (sin cambios esperados) |
| 13 mayo 2026 | Earnings SanDisk (SNDK) |
| 30 junio 2026 | Resolucion mercado "Iran conflict ends June 30" |

---

## Dependencias Python

```
pip install requests pandas yfinance python-dotenv beautifulsoup4 schedule
```
