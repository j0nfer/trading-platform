# -*- coding: utf-8 -*-
"""
scheduler.py — Ejecutor automático de tareas diarias sin necesitar admin.
Corre en background y lanza tarea_diaria.bat a las 9:00h cada día.

INICIAR: python scheduler.py
DETENER: Ctrl+C o cerrar la ventana

Se puede poner en el Startup de Windows para que arranque solo.
"""
import sys, os
sys.path.insert(0, "C:\\inversiones")

import time
import subprocess
import io
from datetime import datetime, date

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "C:\\inversiones"
LOG  = os.path.join(BASE, "logs", "scheduler.log")
BAT  = os.path.join(BASE, "tarea_diaria.bat")

HORA_TAREA = 9   # 9:00 AM
MINUTO_TAREA = 0

os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ts}] {msg}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

def ejecutar_tarea():
    log("Lanzando tarea_diaria.bat...")
    try:
        result = subprocess.run(
            ["cmd", "/c", BAT],
            capture_output=True, text=True, timeout=600,
            cwd=BASE
        )
        log(f"Tarea completada (código: {result.returncode})")
        if result.stdout:
            log(f"Output: {result.stdout[:300]}")
    except subprocess.TimeoutExpired:
        log("ERROR: Tarea superó 10 minutos — cancelada")
    except Exception as e:
        log(f"ERROR: {e}")

def main():
    log("Scheduler iniciado")
    log(f"Tarea programada para las {HORA_TAREA:02d}:{MINUTO_TAREA:02d}h cada día")
    log(f"Script: {BAT}")

    ultimo_dia_ejecutado = None

    while True:
        ahora = datetime.now()
        hoy   = date.today()

        es_hora = (ahora.hour == HORA_TAREA and
                   ahora.minute == MINUTO_TAREA and
                   ultimo_dia_ejecutado != hoy)

        if es_hora:
            ultimo_dia_ejecutado = hoy
            ejecutar_tarea()

        # Calcular tiempo hasta próxima ejecución
        if ahora.hour < HORA_TAREA or (ahora.hour == HORA_TAREA and ahora.minute < MINUTO_TAREA):
            from datetime import timedelta
            proxima = ahora.replace(hour=HORA_TAREA, minute=MINUTO_TAREA, second=0)
        else:
            from datetime import timedelta
            proxima = (ahora + timedelta(days=1)).replace(
                hour=HORA_TAREA, minute=MINUTO_TAREA, second=0)

        faltan = int((proxima - ahora).total_seconds())
        horas, resto = divmod(faltan, 3600)
        minutos = resto // 60

        # Log de estado cada hora
        if ahora.minute == 0:
            log(f"En espera. Próxima ejecución en {horas}h {minutos}m")

        time.sleep(30)  # revisar cada 30 segundos

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Scheduler detenido por el usuario")
