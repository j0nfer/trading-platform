# ESTADO DE SESIÓN — Auto-generado
<!-- Este archivo se actualiza automáticamente al cerrar cada sesión -->
<!-- Claude lo lee al inicio para retomar sin re-establecer contexto -->

## Fecha última actualización
2026-04-04 10:08

## Portfolio (precios al cierre de sesión)

| Posición | Dir | Entrada | Precio actual | P/L | Resuelve |
|---|---|---|---|---|---|
| Pos1 Ceasefire Apr15 (73sh) | NO | 65.7¢ | **94%** | **+21$** | 15 abr (11d) |
| Pos2 Conflict Jun30 (558.8sh) | NO | 24¢ | **44%** | **+115$** | 30 jun (87d) |
| Pos3 WTI $120 YES (289sh) | YES | 51¢ | **77%** | **+75$** | 30 abr (26d) |
| Pos4 InvadeIran NO (457.6sh) | NO | 47¢ | **42%** | **-21$** | 31 dic (271d) |
| **TOTAL P/L** | | | | **+190$** | |

Capital total: $736.21 USDC | Cash: $0.01 (SIN LIQUIDEZ)

## Deadlines críticos
- 🔴 **6 ABRIL** (2 días) — Trump decide si reanuda strikes
- 🟡 **15 ABRIL** (11 días) — Resolución ceasefire Apr15
- ⚪ **30 JUNIO** (87 días) — Resolución conflict ends Jun30

## Contexto macro
- Brent: $109.05
- Insider activo: wallet "NOTHINGEVERFRICKINGHAPPENS" apostó $15.6K a YES Apr15

## Scripts disponibles
```
python -X utf8 analizar_portfolio.py --rapido   # análisis rápido
python -X utf8 comparador_mercados.py --iran    # precios Iran en tiempo real
python -X utf8 telegram_alertas.py --check      # check noticias/precios
python -X utf8 correlacion_posiciones.py        # correlación portfolio
python telegram_alertas.py --setup              # instrucciones bot Telegram
```

## Tarea más urgente al retomar
1. ⚠️  Configurar bot Telegram: @BotFather → TOKEN → .env
2. 🔍 Monitorizar 6 abril (deadline Trump)
3. 📊 Actualizar portfolio.json si precios cambian >5pp
