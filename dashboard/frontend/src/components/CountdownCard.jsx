import { useState, useEffect } from 'react'

const DEADLINES = [
  {
    label:    '⚡ Trump decide strikes',
    date:     new Date('2026-04-06T14:00:00Z'),
    urgencia: 'critica',
    desc:     'Reanuda o pausa bombardeos sobre Irán',
    impacto:  'Afecta directamente ambas posiciones',
  },
  {
    label:    '🟡 Resolución Ceasefire',
    date:     new Date('2026-04-15T21:00:00Z'),
    urgencia: 'alta',
    desc:     'US x Iran ceasefire by April 15?',
    impacto:  'Pos1 NO · entrada 65.7¢',
  },
  {
    label:    '⚪ Resolución Conflict',
    date:     new Date('2026-06-30T21:00:00Z'),
    urgencia: 'normal',
    desc:     'Iran conflict ends by June 30?',
    impacto:  'Pos2 NO · entrada 24¢',
  },
]

function pad(n) {
  return String(n).padStart(2, '0')
}

function calcTimeLeft(target) {
  const diff = target - Date.now()
  if (diff <= 0) return null
  const days  = Math.floor(diff / 86400000)
  const hours = Math.floor((diff % 86400000) / 3600000)
  const mins  = Math.floor((diff % 3600000)  / 60000)
  const secs  = Math.floor((diff % 60000)    / 1000)
  return { days, hours, mins, secs, total: diff }
}

function CountdownTimer({ target, urgencia }) {
  const [left, setLeft] = useState(() => calcTimeLeft(target))

  useEffect(() => {
    const id = setInterval(() => setLeft(calcTimeLeft(target)), 1000)
    return () => clearInterval(id)
  }, [target])

  if (!left) {
    return (
      <div className="text-accent-red font-bold text-sm">
        ⏰ RESUELTO / VENCIDO
      </div>
    )
  }

  const ringColor =
    urgencia === 'critica' ? 'text-accent-red' :
    urgencia === 'alta'    ? 'text-accent-yellow' :
                             'text-slate-400'

  // Urgency flash when < 24h
  const flash = left.days === 0

  return (
    <div className={`flex items-end gap-1 font-mono ${ringColor} ${flash ? 'animate-pulse' : ''}`}>
      {left.days > 0 && (
        <>
          <div className="text-center">
            <div className="text-2xl font-bold leading-none">{left.days}</div>
            <div className="text-xs opacity-60 mt-0.5">días</div>
          </div>
          <div className="text-xl pb-3 opacity-40">:</div>
        </>
      )}
      <div className="text-center">
        <div className="text-2xl font-bold leading-none">{pad(left.hours)}</div>
        <div className="text-xs opacity-60 mt-0.5">h</div>
      </div>
      <div className="text-xl pb-3 opacity-40">:</div>
      <div className="text-center">
        <div className="text-2xl font-bold leading-none">{pad(left.mins)}</div>
        <div className="text-xs opacity-60 mt-0.5">min</div>
      </div>
      <div className="text-xl pb-3 opacity-40">:</div>
      <div className="text-center">
        <div className="text-2xl font-bold leading-none">{pad(left.secs)}</div>
        <div className="text-xs opacity-60 mt-0.5">seg</div>
      </div>
    </div>
  )
}

// Mini progress bar: % of time elapsed since "now - totalDays" to deadline
function TimeBar({ target, totalDays, urgencia }) {
  const elapsed = 1 - (target - Date.now()) / (totalDays * 86400000)
  const pct     = Math.max(0, Math.min(100, elapsed * 100))
  const color   =
    urgencia === 'critica' ? 'bg-accent-red' :
    urgencia === 'alta'    ? 'bg-accent-yellow' :
                             'bg-slate-400'
  return (
    <div className="h-1 bg-dark-600 rounded-full mt-3 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

const TOTAL_DAYS = [3, 12, 88]  // días totales desde inicio de sesión (aprox)

export default function CountdownCard() {
  return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6">
      <h2 className="text-white font-bold text-lg mb-5">⏱️ Deadlines</h2>

      <div className="space-y-5">
        {DEADLINES.map((d, i) => (
          <div
            key={i}
            className={`rounded-lg p-4 border ${
              d.urgencia === 'critica'
                ? 'border-accent-red/40 bg-accent-red/5'
                : d.urgencia === 'alta'
                ? 'border-accent-yellow/30 bg-accent-yellow/5'
                : 'border-dark-600 bg-dark-700'
            }`}
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <div>
                <div className="text-sm font-bold text-white">{d.label}</div>
                <div className="text-xs text-slate-500 mt-0.5">{d.desc}</div>
                <div className="text-xs text-slate-600 mt-0.5">{d.impacto}</div>
              </div>
              <CountdownTimer target={d.date} urgencia={d.urgencia} />
            </div>
            <TimeBar target={d.date} totalDays={TOTAL_DAYS[i]} urgencia={d.urgencia} />
          </div>
        ))}
      </div>
    </div>
  )
}
