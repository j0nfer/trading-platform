import { useApi } from '../hooks/useApi'

function fmt(v, decimals = 2) {
  if (v == null) return '—'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toFixed(decimals)
}

function fmtUSD(v) {
  if (v == null) return '—'
  const n = Number(v)
  return (n >= 0 ? '+$' : '-$') + Math.abs(n).toFixed(2)
}

export default function Header() {
  const { data, loading, error, lastOk } = useApi('/portfolio/summary', 15000)

  const pnl = data?.total_pnl ?? null
  const pnlColor = pnl == null ? 'text-slate-400'
    : pnl >= 0 ? 'text-accent-green' : 'text-accent-red'

  return (
    <header className="bg-dark-800 border-b border-dark-600 px-6 py-3 flex items-center justify-between">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="text-accent-blue font-bold text-xl tracking-tight">
          📊 Trading Platform
        </div>
        <span className="text-slate-500 text-sm">Jon · Polymarket</span>
      </div>

      {/* P/L Global */}
      {!loading && !error && data && (
        <div className="flex items-center gap-6 text-sm">
          <div className="text-center">
            <div className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">P/L Total</div>
            <div className={`font-bold text-lg ${pnlColor}`}>
              {fmtUSD(data.total_pnl)}
            </div>
          </div>
          <div className="text-center">
            <div className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">Pos1 NO</div>
            <div className="text-white font-mono">{data.pos1_no != null ? (data.pos1_no * 100).toFixed(1) + '%' : '—'}</div>
          </div>
          <div className="text-center">
            <div className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">Pos2 NO</div>
            <div className="text-white font-mono">{data.pos2_no != null ? (data.pos2_no * 100).toFixed(1) + '%' : '—'}</div>
          </div>
          <div className="text-center">
            <div className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">Apr15</div>
            <div className="font-mono text-accent-yellow">{data.dias_pos1}d</div>
          </div>
          <div className="text-center">
            <div className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">Jun30</div>
            <div className="font-mono text-slate-300">{data.dias_pos2}d</div>
          </div>
        </div>
      )}

      {/* Live indicator */}
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span className="w-2 h-2 rounded-full bg-accent-green pulse-dot inline-block" />
        {loading ? 'Cargando...' : error ? `Error: ${error}` : `Actualizado ${lastOk?.toLocaleTimeString('es-ES')}`}
      </div>
    </header>
  )
}
