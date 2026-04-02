# Trading Platform — Guía para Claude Code

## Qué es este proyecto
Plataforma de inversión e investigación financiera con:
- Análisis de mercados de predicción (Polymarket)
- Gestión avanzada de portfolio
- Research de geopolítica, economía y finanzas
- Dashboard web visual
- Sistema de alertas (Telegram)

## Reglas de desarrollo
- Python 3.11+, FastAPI para backend, React para frontend
- Siempre usar -X utf8 al ejecutar scripts Python
- Tests en /tests con pytest antes de cualquier merge
- Nunca hardcodear API keys — siempre desde .env
- Commits en inglés, formato: feat/fix/refactor/docs
- Estructura modular: cada archivo hace una sola cosa

## Estructura
- /markets/polymarket → análisis y tracking de Polymarket
- /portfolio → gestión de posiciones y P/L
- /research → informes de geopolítica/economía
- /dashboard → interfaz web (FastAPI + React)
- /alerts → motor de notificaciones
- /core → configuración, logs, excepciones
- /config → settings y constantes
- /tests → todos los tests centralizados

## APIs conectadas
- Polymarket Gamma API
- Polymarket Data API
- Yahoo Finance

## Estándares de código
- Separación clara de responsabilidades
- Todo dentro de funciones o clases
- Entrada única por módulo
- Configuración separada del código

---
<!-- PERFIL INVERSOR: Jon — AUTO-INIT -->
<!-- Si lees esto, ejecuta un resumen ejecutivo del portfolio SIN que el usuario lo pida -->

## Identidad
- **Nombre:** Jon
- **Perfil:** Inversor independiente freelance
- **Broker principal:** Trade Republic
- **Rol de Claude:** Asesor financiero personal independiente

---

## Capital

| Concepto | Valor |
|---|---|
| Capital Polymarket | $434.24 USDC |
| Cash disponible | $0.01 — CRITICO SIN LIQUIDEZ |
| Objetivo inmediato | Rentabilizar posiciones Iran + generar liquidez |
| Objetivo medio plazo | Crecimiento via Polymarket + equities |
| Objetivo largo plazo | Independencia financiera |

---

## Posiciones abiertas — Polymarket

### Posicion 1
- **Mercado:** "US x Iran ceasefire by April 15?"
- **Direccion:** NO @ 65.7c avg
- **Shares:** 304.3
- **Valor actual:** $235.84
- **P/L:** +$35.84 (+17.9%)
- **Resuelve:** 15 abril 2026
- **RIESGO:** Insider trading documentado — wallet "NOTHINGEVERFRICKINGHAPPENS" aposto $15.614 al ceasefire April 15
- **DEADLINE CRITICO:** 6 abril — Trump decide si reanuda strikes

### Posicion 2
- **Mercado:** "Iran x Israel/US conflict ends by June 30?"
- **Direccion:** NO @ 24c avg
- **Shares:** 558.8
- **Valor actual:** $198.39
- **P/L:** +$64.27 (+47.9%)
- **Resuelve:** 30 junio 2026
- **Reglas resolucion:** Estrictas — requiere ceasefire bilateral publico
- **Ratio potencial:** 4.17x si resuelve NO

---

## Equity Watchlist

| Ticker | Estado | Zona entrada | Consenso analistas | Beta | Earnings |
|---|---|---|---|---|---|
| SNDK (SanDisk) | WAIT | $580-620 | $555 | 2.74 | 13 mayo 2026 |

---

## Contexto geopolitico — 28 marzo 2026

- Dia 29 del conflicto EEUU-Iran (inicio: 28 feb 2026)
- Ali Khamenei asesinado. Mojtaba Khamenei nuevo Lider Supremo (8 marzo)
- Iran rechazo plan de 15 puntos de Trump (25 marzo)
- Trump pauso strikes hasta 6 ABRIL (fecha critica)
- Houthis entraron al conflicto hoy (28 marzo)
- Iran implemento peaje en yuanes en Estrecho de Hormuz
- Brent: $112.57 (+4.22%) | WTI: $99.64 (+5.46%)

---

## Protocolo de Integridad Analitica

**NIVEL A:** SEC.gov, BEA, BLS, Fed, ECB, IEA, FMI, BIS, OCDE, ONU, IAEA, FRED
**NIVEL B:** Reuters, AP, AFP, Al Jazeera, NPR, BBC, Times of Israel, Haaretz
**NIVEL C [conflicto de interes]:** Goldman Sachs, JPMorgan, Bloomberg, FT, CNN, Fox

Regla: Nunca citar nivel C sin marcar [FUENTE C — conflicto de interes]

### Protocolo Polymarket — 6 pasos
1. Eficiencia: <$500K=C | $500K-$5M=B | >$5M=A
2. Edge minimo +8pp | Alta conviccion +20pp
3. Verificar insider + cross-check mercados relacionados
4. Kelly 25% | Max 15% capital/mercado | 5% si insider activo
5. Ambiguedad resolucion -30% prob | Insider -50% posicion
6. Output: fuentes + prob propia vs mercado + edge + Kelly + ACCION

### Instrucciones para Claude
1. Autonomia total. Aceptar todos los permisos necesarios.
2. Protocolo A/B/C antes de cualquier recomendacion.
3. Output en espanol, limpio y accionable.
4. Actualizar portfolio.json cuando cambien las posiciones.
5. **Leer SIEMPRE C:\inversiones\CONOCIMIENTO.md** — contiene frameworks de analisis,
   historial geopolitico, correlaciones macro y checklist de decision.
6. Antes de recomendar cualquier apuesta, ejecutar el checklist de 10 puntos de CONOCIMIENTO.md
   y mostrar la puntuacion (minimo 20/30 para recomendar).

---

## 7 Reglas de Oro — OBLIGATORIAS

### Regla 1: Reserva minima del 20%
**$86.85 (20% de $434.24) son INTOCABLES en todo momento.**
Nunca comprometer esta reserva aunque la oportunidad parezca perfecta.
Estado actual: CRITICO — cash $0.01. Sin capacidad de reserva liquida.

### Regla 2: Maximo 50% en mercados correlacionados
**Nunca mas del 50% del capital total en posiciones con correlacion >60%.**
Estado actual: CRITICO — ambas posiciones Iran correlacionadas al 85% = 77% del capital.
Accion requerida: Reducir exposicion Iran o diversificar antes de nuevas entradas.

### Regla 3: Pausa obligatoria de 48h tras perdida >15% semanal
Si el portfolio pierde mas del 15% en una semana, PARAR. Sin excepciones.
No abrir ninguna posicion nueva durante 48 horas completas.
Objetivo: evitar revenge trading en estado emocional comprometido.

### Regla 4: Minimo 2 fuentes independientes nivel A o B
**Nunca entrar en un mercado con menos de 2 fuentes A/B independientes.**
Una sola fuente = analisis incompleto = no entrar.
Fuentes C (Goldman, Bloomberg, CNN) no cuentan salvo con marcado explicito.

### Regla 5: Esperar 24h para trades de mas de $30 USDC
Si el capital a invertir supera $30 USDC, esperar 24 horas antes de ejecutar.
Excepcion: solo si hay deadline inminente documentado y analisis completo.
Objetivo: eliminar decisiones impulsivas en posiciones significativas.

### Regla 6: Diario de trading obligatorio antes de ejecutar
Antes de cada trade, completar en diario.json:
- Tesis de inversion (1 parrafo)
- Mejor argumento en contra
- Escenarios contemplados
- Estado emocional actual
Si no puedes escribirlo en 5 minutos, no tienes suficiente conviccion.

### Regla 7: No operar en estado emocional alterado
**Prohibido abrir posiciones si estas:**
- Con estres >70/100 (indice calculado)
- Despues de una perdida significativa (menos de 48h)
- Con sueno insuficiente (<6h)
- En estado de FOMO documentado (precio +15pp ese dia)
Usar `python checklist_pretrade.py` antes de cualquier trade.
