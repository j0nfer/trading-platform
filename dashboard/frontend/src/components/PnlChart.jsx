import { useApi } from '../hooks/useApi'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'

// Custom tooltip
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="bg-dark-800 border border-dark-600 rounded-lg p-3 text-xs shadow-xl">
      <div className="text-slate-400 mb-2 font-bold">{label}</div>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-slate-400">P/L Total</span>
          <span className={`font-bold ${d?.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
            {d?.pnl >= 0 ? '+' : ''}{d?.pnl?.toFixed(2)}$
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-slate-500">Pos1 (Apr15)</span>
          <span className={d?.pnl_pos1 >= 0 ? 'text-accent-green' : 'text-accent-red'}>
            {d?.pnl_pos1 >= 0 ? '+' : ''}{d?.pnl_pos1?.toFixed(2)}$
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-slate-500">Pos2 (Jun30)</span>
          <span className={d?.pnl_pos2 >= 0 ? 'text-accent-green' : 'text-accent-red'}>
            {d?.pnl_pos2 >= 0 ? '+' : ''}{d?.pnl_pos2?.toFixed(2)}$
          </span>
        </div>
        <div className="border-t border-dark-600 pt-1 mt-1 flex justify-between gap-4">
          <span className="text-slate-500">NO Pos1</span>
          <span className="text-slate-300">{d?.no_pos1 != null ? (d.no_pos1 * 100).toFixed(1) + '%' : '—'}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-slate-500">NO Pos2</span>
          <span className="text-slate-300">{d?.no_pos2 != null ? (d.no_pos2 * 100).toFixed(1) + '%' : '—'}</span>
        </div>
        {d?.live && <div className="text-accent-blue text-xs mt-1">● live</div>}
        {d?.seed && <div className="text-slate-600 text-xs mt-1">~ estimado</div>}
      </div>
    </div>
  )
}

function formatFecha(str) {
  if (!str) return ''
  const [, m, d] = str.split('-')
  return `${d}/${m}`
}

export default function PnlChart() {
  const { data, loading, error } = useApi('/history?dias=14', 120000)

  if (loading) return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6 animate-pulse">
      <div className="h-4 bg-dark-600 rounded w-1/3 mb-4" />
      <div className="h-48 bg-dark-700 rounded-lg" />
    </div>
  )

  if (error) return (
    <div className="bg-dark-800 rounded-xl border border-accent-red/30 p-6">
      <p className="text-accent-red text-sm">Error cargando histórico: {error}</p>
    </div>
  )

  const puntos = (data?.puntos ?? []).map(p => ({
    ...p,
    fechaLabel: formatFecha(p.fecha),
  }))

  const maxPnl  = Math.max(...puntos.map(p => p.pnl), 0)
  const minPnl  = Math.min(...puntos.map(p => p.pnl), 0)
  const ultimo  = puntos[puntos.length - 1]
  const positivo = (ultimo?.pnl ?? 0) >= 0

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white font-bold text-lg">📈 Histórico P/L</h2>
        <div className="flex items-center gap-3">
          {ultimo && (
            <div className={`text-lg font-bold font-mono ${positivo ? 'text-accent-green' : 'text-accent-red'}`}>
              {positivo ? '+' : ''}{ultimo.pnl?.toFixed(2)}$
            </div>
          )}
          {data?.puntos?.some(p => p.seed) && (
            <span className="text-xs text-slate-600 bg-dark-700 px-2 py-0.5 rounded">
              ~ datos estimados
            </span>
          )}
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={puntos} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="gradPnl" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#00d4a0" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#00d4a0" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradPos1" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#3d9eff" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#3d9eff" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#1e2847" vertical={false} />

          <XAxis
            dataKey="fechaLabel"
            tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${v > 0 ? '+' : ''}${v}$`}
            width={55}
          />

          <Tooltip content={<CustomTooltip />} />

          {/* Zero line */}
          <ReferenceLine y={0} stroke="#334155" strokeDasharray="4 4" />

          {/* Pos1 P/L area */}
          <Area
            type="monotone"
            dataKey="pnl_pos1"
            stroke="#3d9eff"
            strokeWidth={1.5}
            fill="url(#gradPos1)"
            dot={false}
            name="Pos1 Apr15"
          />

          {/* Total P/L area (main) */}
          <Area
            type="monotone"
            dataKey="pnl"
            stroke="#00d4a0"
            strokeWidth={2.5}
            fill="url(#gradPnl)"
            dot={(props) => {
              const { cx, cy, payload } = props
              if (!payload.live) return null
              return (
                <circle
                  key={`dot-${cx}`}
                  cx={cx} cy={cy} r={5}
                  fill="#00d4a0"
                  stroke="#0a0e1a"
                  strokeWidth={2}
                />
              )
            }}
            name="P/L Total"
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Legend manual */}
      <div className="flex gap-4 mt-3 text-xs text-slate-500 justify-center">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-0.5 bg-accent-green rounded" />
          <span>P/L Total</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-0.5 bg-accent-blue rounded" />
          <span>Pos1 Ceasefire Apr15</span>
        </div>
      </div>
    </div>
  )
}
