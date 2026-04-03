import { useState } from 'react'
import { useApi } from '../hooks/useApi'

const SEÑAL_STYLES = {
  FUERTE_FAVOR:   { color: 'text-accent-green', bg: 'bg-accent-green/20', label: '🟢 FUERTE A FAVOR' },
  MODERADO_FAVOR: { color: 'text-accent-green', bg: 'bg-accent-green/10', label: '🟩 MODERADO FAVOR' },
  NEUTRAL:        { color: 'text-slate-400',    bg: 'bg-slate-400/10',    label: '⬜ NEUTRAL' },
  MODERADO_CONTRA:{ color: 'text-accent-red',   bg: 'bg-accent-red/10',   label: '🟥 MODERADO CONTRA' },
  FUERTE_CONTRA:  { color: 'text-accent-red',   bg: 'bg-accent-red/20',   label: '🔴 FUERTE CONTRA' },
}

function MarketWhales({ nombre, data }) {
  const [expanded, setExpanded] = useState(false)
  if (!data) return null

  const señal = SEÑAL_STYLES[data.señal] ?? SEÑAL_STYLES.NEUTRAL
  const total = data.vol_favor + data.vol_contra
  const favorPct = total > 0 ? (data.vol_favor / total) * 100 : 50

  return (
    <div className="bg-dark-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{nombre}</div>
          <div className={`text-sm font-bold ${señal.color}`}>{señal.label}</div>
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>{data.n_whales} whales</div>
          <div>≥$500</div>
        </div>
      </div>

      {/* Ratio bar */}
      <div className="h-2 bg-accent-red/40 rounded-full mb-2 overflow-hidden">
        <div
          className="h-full bg-accent-green transition-all rounded-full"
          style={{ width: `${favorPct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-accent-green">Favor ${data.vol_favor?.toFixed(0)}</span>
        <span className="text-accent-red">Contra ${data.vol_contra?.toFixed(0)}</span>
      </div>

      {/* Top whales table */}
      {data.whales?.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-3 text-xs text-slate-500 hover:text-accent-blue transition-colors"
          >
            {expanded ? '▲ Ocultar' : '▼ Ver trades'} ({data.whales.length})
          </button>
          {expanded && (
            <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
              {data.whales.map((w, i) => (
                <div
                  key={i}
                  className={`flex items-center justify-between text-xs px-2 py-1 rounded ${
                    w.a_favor ? 'bg-accent-green/10' : 'bg-accent-red/10'
                  }`}
                >
                  <span className="font-mono text-slate-400 truncate max-w-[120px]">{w.wallet}</span>
                  <span className="text-slate-300">{w.outcome} {w.side}</span>
                  <span className={`font-bold ${w.a_favor ? 'text-accent-green' : 'text-accent-red'}`}>
                    ${w.size?.toFixed(0)}
                  </span>
                  <span className="text-slate-500">{w.hora}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function WhalesCard() {
  const { data, loading, error } = useApi('/whales?horas=6&umbral=500', 45000)

  if (loading) return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6 animate-pulse">
      <div className="h-4 bg-dark-600 rounded w-1/3 mb-4" />
      <div className="space-y-3">
        <div className="h-28 bg-dark-700 rounded-lg" />
        <div className="h-28 bg-dark-700 rounded-lg" />
      </div>
    </div>
  )

  if (error) return (
    <div className="bg-dark-800 rounded-xl border border-accent-red/30 p-6">
      <p className="text-accent-red text-sm">Error cargando whales: {error}</p>
    </div>
  )

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-white font-bold text-lg">🐋 Whales</h2>
        <span className="text-xs text-slate-500">
          Últimas {data?.parametros?.horas ?? 6}h · ≥${data?.parametros?.umbral ?? 500}
        </span>
      </div>

      <div className="space-y-4">
        <MarketWhales nombre="Ceasefire Apr15" data={data?.ceasefire_apr15} />
        <MarketWhales nombre="Conflict Jun30"  data={data?.conflict_jun30} />
      </div>
    </div>
  )
}
