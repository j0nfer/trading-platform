import { useApi } from '../hooks/useApi'

function PriceGauge({ yes, no, label }) {
  const yesPct  = Math.round((yes ?? 0) * 100)
  const noPct   = Math.round((no ?? 0) * 100)

  return (
    <div>
      <div className="text-xs text-slate-500 mb-2 truncate">{label}</div>
      {/* Bar */}
      <div className="h-5 rounded-md overflow-hidden flex text-xs font-bold">
        <div
          className="flex items-center justify-center bg-accent-green/80 text-dark-900 transition-all"
          style={{ width: `${yesPct}%` }}
        >
          {yesPct > 12 ? `YES ${yesPct}%` : ''}
        </div>
        <div
          className="flex items-center justify-center bg-accent-red/80 text-dark-900 transition-all"
          style={{ width: `${noPct}%` }}
        >
          {noPct > 12 ? `NO ${noPct}%` : ''}
        </div>
      </div>
      {/* Values */}
      <div className="flex justify-between mt-1 text-xs text-slate-400">
        <span className="text-accent-green">YES {(yes * 100).toFixed(1)}¢</span>
        <span className="text-accent-red">NO {(no * 100).toFixed(1)}¢</span>
      </div>
    </div>
  )
}

export default function PricesCard() {
  const { data, loading, error, lastOk } = useApi('/prices', 15000)

  if (loading) return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6 animate-pulse">
      <div className="h-4 bg-dark-600 rounded w-1/3 mb-4" />
      <div className="space-y-5">
        <div className="h-16 bg-dark-700 rounded-lg" />
        <div className="h-16 bg-dark-700 rounded-lg" />
      </div>
    </div>
  )

  if (error) return (
    <div className="bg-dark-800 rounded-xl border border-accent-red/30 p-6">
      <p className="text-accent-red text-sm">Error cargando precios: {error}</p>
    </div>
  )

  const c1 = data?.ceasefire_apr15
  const c2 = data?.conflict_jun30

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-white font-bold text-lg">💹 Precios Live</h2>
        <div className="text-xs text-slate-500">
          {lastOk ? `${lastOk.toLocaleTimeString('es-ES')}` : ''}
        </div>
      </div>

      <div className="space-y-5">
        {c1 && !c1.error && (
          <div className="bg-dark-700 rounded-lg p-4">
            <PriceGauge yes={c1.yes} no={c1.no} label="Ceasefire Apr15" />
            <div className="mt-2 text-xs text-slate-500">
              Vol: ${(c1.vol / 1000).toFixed(0)}K · Res: {c1.end_date?.slice(0, 10)}
            </div>
          </div>
        )}
        {c2 && !c2.error && (
          <div className="bg-dark-700 rounded-lg p-4">
            <PriceGauge yes={c2.yes} no={c2.no} label="Conflict Jun30" />
            <div className="mt-2 text-xs text-slate-500">
              Vol: ${(c2.vol / 1000).toFixed(0)}K · Res: {c2.end_date?.slice(0, 10)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
