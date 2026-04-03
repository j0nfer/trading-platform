@echo off
:: ============================================================
:: TAREA DIARIA — Portfolio Jon
:: Se ejecuta automáticamente a las 9:00h via Task Scheduler
:: Output guardado en: C:\inversiones\logs\diario_YYYY-MM-DD.txt
:: ============================================================

cd /d "C:\inversiones"

:: Crear carpeta logs si no existe
if not exist "C:\inversiones\logs" mkdir "C:\inversiones\logs"

:: Nombre del log de hoy
for /f "tokens=1-3 delims=/" %%a in ("%date%") do set HOY=%%c-%%b-%%a
set LOG=C:\inversiones\logs\diario_%HOY%.txt

echo ============================================================ > "%LOG%"
echo   ANALISIS DIARIO AUTOMATICO — %date% %time% >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo. >> "%LOG%"

:: 1. Actualizar estado del portfolio con precios reales
echo [1/4] Actualizando estado portfolio... >> "%LOG%"
python "C:\inversiones\core\guardar_estado.py" >> "%LOG%" 2>&1

:: 2. Cross-check silencioso (solo log, sin Telegram)
echo. >> "%LOG%"
echo [2/4] Cross-check mercados (silencioso)... >> "%LOG%"
python -X utf8 "C:\inversiones\markets\polymarket\comparador_mercados.py" --iran >> "%LOG%" 2>&1

:: 3. Scan de oportunidades (sin Telegram — solo si score>=80 envia)
echo. >> "%LOG%"
echo [3/4] Motor: scan oportunidades + whales... >> "%LOG%"
python -X utf8 "C:\inversiones\alerts\motor_alertas.py" --test >> "%LOG%" 2>&1

:: 3b. Watchlist — check de oportunidades vs precios base
echo. >> "%LOG%"
echo [3b] Watchlist: check oportunidades... >> "%LOG%"
python -X utf8 "C:\inversiones\markets\polymarket\watchlist.py" --check >> "%LOG%" 2>&1

:: 3c. Comparador odds — detectar gaps Polymarket vs sportsbooks
echo. >> "%LOG%"
echo [3c] Comparador odds: gaps externos... >> "%LOG%"
python -X utf8 "C:\inversiones\markets\polymarket\comparador_odds.py" --nhl >> "%LOG%" 2>&1

:: 3d. Patrones historicos — base rates para posiciones abiertas
echo. >> "%LOG%"
echo [3d] Analizador patrones: base rates Venezuela+Iran... >> "%LOG%"
python -X utf8 "C:\inversiones\research\sources\analizador_patrones.py" --all >> "%LOG%" 2>&1

:: 3e. Inteligencia multi-fuente — top noticias Iran + Venezuela
echo. >> "%LOG%"
echo [3e] Fuentes avanzadas: Iran + Venezuela top 5 c/u... >> "%LOG%"
python -X utf8 "C:\inversiones\research\sources\fuentes_avanzadas.py" --iran --top 5 >> "%LOG%" 2>&1
python -X utf8 "C:\inversiones\research\sources\fuentes_avanzadas.py" --venezuela --top 5 >> "%LOG%" 2>&1

:: 3f. Whale tracker — actividad grandes jugadores en posiciones abiertas
echo. >> "%LOG%"
echo [3f] Whale tracker: actividad whales ultimas 24h... >> "%LOG%"
python -X utf8 "C:\inversiones\markets\polymarket\whale_tracker.py" --horas 24 --umbral 500 --alerta 3000 --log >> "%LOG%" 2>&1

:: 4. UN SOLO mensaje diario con todo el resumen
echo. >> "%LOG%"
echo [4/4] Enviando resumen diario Telegram... >> "%LOG%"
python -X utf8 "C:\inversiones\alerts\telegram_alertas.py" --diario >> "%LOG%" 2>&1

:: 6. Lanzar Bot de Inteligencia Geopolitica en background (monitoreo continuo cada 10 min)
echo. >> "%LOG%"
echo [6/6] Iniciando Bot Inteligencia Geopolitica en background... >> "%LOG%"
tasklist /FI "WINDOWTITLE eq Bot Inteligencia*" 2>nul | find /I "cmd.exe" >nul
if errorlevel 1 (
    start "Bot Inteligencia Geopolitica" /MIN pythonw.exe "C:\inversiones\alerts\bot_inteligencia.py"
    echo Bot de inteligencia iniciado en background. >> "%LOG%"
) else (
    echo Bot de inteligencia ya estaba en ejecucion. >> "%LOG%"
)

echo. >> "%LOG%"
echo Tarea completada: %time% >> "%LOG%"

:: Limpiar logs de más de 30 días
forfiles /p "C:\inversiones\logs" /m "diario_*.txt" /d -30 /c "cmd /c del @file" 2>nul

exit /b 0
