import { useApi } from '../hooks/useApi'

function PnlBadge({ value }) {
  if (value == null) return null
  const positive = value >= 0
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${
      positive ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-red/20 text-accent-red'
    }`}>
      {positive ? '+' : ''}{value.toFixed(2)}$
    </span>
  )
}

function PnlPct({ value }) {
  if (value == null) return null
  const positive = value >= 0
  return (
    <span className={`text-sm font-mono ${positive ? 'text-accent-green' : 'text-accent-red'}`}>
      {positive ? '+' : ''}{value.toFixed(1)}%
    </span>
  )
}

function ProgressBar({ entry, current }) {
  // Shows price movement from entry to current
  const min = Math.min(entry, current, 0)
  const max = Math.max(entry, current, 1)
  const entryPct = ((entry - min) / (max - min)) * 100
  const currentPct = ((current - min) / (max - min)) * 100
  const winning = current > entry

  return (
    <div className="relative h-1.5 bg-dark-600 rounded-full mt-2">
      {/* Entry marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 w-0.5 h-3 bg-slate-400 rounded-full z-10"
        style={{ left: `${entryPct}%` }}
        title={`Entrada: ${(entry * 100).toFixed(1)}¢`}
      />
      {/* Current fill */}
      <div
        className={`absolute left-0 top-0 h-full rounded-full ${winning ? 'bg-accent-green' : 'bg-accent-red'}`}
        style={{ width: `${currentPct}%` }}
      />
    </div>
  )
}

export default function PortfolioCard() {
  const { data, loading, error } = useApi('/portfolio', 20000)

  if (loading) return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6 glow-blue animate-pulse">
      <div className="h-4 bg-dark-600 rounded w-1/3 mb-4" />
      <div className="space-y-3">
        <div className="h-24 bg-dark-700 rounded-lg" />
        <div className="h-24 bg-dark-700 rounded-lg" />
      </div>
    </div>
  )

  if (error) return (
    <div className="bg-dark-800 rounded-xl border border-accent-red/30 p-6">
      <p className="text-accent-red text-sm">Error cargando portfolio: {error}</p>
    </div>
  )

  const posiciones = data?.posiciones ?? []
  const resumen    = data?.resumen ?? {}

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6 glow-blue">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-white font-bold text-lg">📈 Portfolio</h2>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-slate-400">Total P/L:</span>
          <PnlBadge value={resumen.total_pnl} />
          <span className={`font-mono text-sm ${
            (resumen.total_pnl_pct ?? 0) >= 0 ? 'text-accent-green' : 'text-accent-red'
          }`}>
            {(resumen.total_pnl_pct ?? 0) >= 0 ? '+' : ''}{(resumen.total_pnl_pct ?? 0).toFixed(1)}%
          </span>
        </div>
      </div>

      <div className="space-y-4">
        {posiciones.map((pos, i) => (
          <div
            key={pos.id}
            className="bg-dark-700 rounded-lg p-4 border border-dark-600 hover:border-accent-blue/40 transition-colors"
          >
            {/* Header row */}
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">
                  Pos {i + 1} · {pos.direccion}
                </div>
                <div className="text-white text-sm font-medium leading-snug max-w-xs">
                  {pos.mercado}
                </div>
              </div>
              <div className="text-right">
                <PnlBadge value={pos.pnl_absoluto} />
                <div className="mt-1">
                  <PnlPct value={pos.pnl_pct} />
                </div>
              </div>
            </div>

            {/* Price row */}
            <div className="grid grid-cols-4 gap-2 text-xs mb-2">
              <div>
                <div className="text-slate-500 mb-0.5">Entrada</div>
                <div className="font-mono text-slate-300">{(pos.entrada * 100).toFixed(1)}¢</div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">NO actual</div>
                <div className={`font-mono font-bold ${
                  pos.precio_actual > pos.entrada ? 'text-accent-green' : 'text-accent-red'
                }`}>
                  {(pos.precio_actual * 100).toFixed(1)}¢
                  <span className="text-slate-500 text-xs ml-1">
                    {pos.fuente_precio === 'live' ? '●' : '○'}
                  </span>
                </div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">Shares</div>
                <div className="font-mono text-slate-300">{pos.shares.toFixed(0)}</div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">Resuelve</div>
                <div className={`font-mono ${pos.dias_restantes <= 14 ? 'text-accent-yellow' : 'text-slate-300'}`}>
                  {pos.dias_restantes}d
                </div>
              </div>
            </div>

            {/* Progress bar */}
            <ProgressBar entry={pos.entrada} current={pos.precio_actual} />

            {/* Footer */}
            <div className="flex justify-between mt-2 text-xs text-slate-500">
              <span>Costo: ${pos.costo?.toFixed(2)}</span>
              <span>Valor: ${pos.valor?.toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Resumen bottom */}
      <div className="mt-4 pt-4 border-t border-dark-600 grid grid-cols-3 gap-3 text-sm">
        <div className="text-center">
          <div className="text-slate-500 text-xs mb-1">Capital total</div>
          <div className="font-mono text-white">${resumen.capital_total?.toFixed(2)}</div>
        </div>
        <div className="text-center">
          <div className="text-slate-500 text-xs mb-1">Invertido</div>
          <div className="font-mono text-white">${resumen.total_costo?.toFixed(2)}</div>
        </div>
        <div className="text-center">
          <div className="text-slate-500 text-xs mb-1">Cash libre</div>
          <div className={`font-mono ${(resumen.cash ?? 0) < 10 ? 'text-accent-red' : 'text-white'}`}>
            ${resumen.cash?.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  )
}
