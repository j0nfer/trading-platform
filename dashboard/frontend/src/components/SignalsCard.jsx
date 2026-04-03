import { useApi } from '../hooks/useApi'

const URGENCIA_STYLES = {
  CRITICA:  'border-l-accent-red bg-accent-red/10 text-accent-red',
  ALTA:     'border-l-accent-yellow bg-accent-yellow/10 text-accent-yellow',
  MEDIA:    'border-l-accent-blue bg-accent-blue/10 text-accent-blue',
  BAJA:     'border-l-slate-400 bg-slate-400/10 text-slate-400',
}

const ACCION_ICONS = {
  VENDER_INMEDIATO: '🚨',
  EVALUAR_VENTA:    '⚠️',
  CONSIDERAR_COMPRA:'💡',
  MONITORIZAR:      '👁️',
  PREPARAR_SALIDA:  '🏁',
}

export default function SignalsCard() {
  const { data, loading, error, refetch } = useApi('/signals', 60000)

  if (loading) return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6 animate-pulse">
      <div className="h-4 bg-dark-600 rounded w-1/3 mb-4" />
      <div className="space-y-3">
        {[1, 2].map(i => <div key={i} className="h-16 bg-dark-700 rounded-lg" />)}
      </div>
    </div>
  )

  const señales = data?.señales ?? []
  const n = data?.n_señales ?? 0

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-white font-bold text-lg">
          ⚡ Señales
          {n > 0 && (
            <span className="ml-2 text-xs bg-accent-red/30 text-accent-red px-2 py-0.5 rounded-full">
              {n}
            </span>
          )}
        </h2>
        <button
          onClick={refetch}
          className="text-xs text-slate-500 hover:text-accent-blue transition-colors"
        >
          ↻ Actualizar
        </button>
      </div>

      {error && <p className="text-accent-red text-sm mb-3">Error: {error}</p>}

      {señales.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          <div className="text-4xl mb-2">✅</div>
          <div className="text-sm">Sin señales activas — mercado estable</div>
        </div>
      ) : (
        <div className="space-y-3">
          {señales.map((s, i) => {
            const style = URGENCIA_STYLES[s.urgencia] ?? URGENCIA_STYLES.BAJA
            const icon  = ACCION_ICONS[s.accion] ?? '📌'
            return (
              <div
                key={i}
                className={`border-l-4 rounded-r-lg p-3 ${style}`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg">{icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-bold uppercase tracking-wide opacity-80">
                        {s.tipo}
                      </span>
                      <span className="text-xs opacity-60">{s.mercado}</span>
                    </div>
                    <div className="text-sm">{s.mensaje}</div>
                    <div className="mt-1 text-xs opacity-60 font-mono">
                      Acción sugerida: {s.accion}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
