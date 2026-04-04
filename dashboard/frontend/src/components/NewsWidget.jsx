import { useState } from 'react'
import { useApi } from '../hooks/useApi'

const PRIORITY_STYLE = {
  CRITICA: { badge: 'bg-accent-red/20 text-accent-red border border-accent-red/40',     dot: 'bg-accent-red',    label: 'CRÍTICA' },
  ALTA:    { badge: 'bg-accent-yellow/20 text-accent-yellow border border-accent-yellow/40', dot: 'bg-accent-yellow', label: 'ALTA' },
  MEDIA:   { badge: 'bg-accent-blue/20 text-accent-blue border border-accent-blue/40',   dot: 'bg-accent-blue',   label: 'MEDIA' },
  BAJA:    { badge: 'bg-slate-700 text-slate-400 border border-slate-600',               dot: 'bg-slate-500',     label: 'BAJA' },
}

const MARKET_LABEL = {
  iran_ceasefire: '🕊️ Ceasefire',
  iran_conflict:  '⚔️ Conflicto',
  wti_oil:        '🛢️ WTI',
  iran_invasion:  '🪖 Invasión',
  macro:          '📊 Macro',
  general:        '🌐 General',
}

function StatsBar({ stats }) {
  if (!stats) return null
  const total = stats.total || 0
  if (total === 0) return <span className="text-slate-600 text-xs">Sin noticias recientes</span>

  return (
    <div className="flex items-center gap-2 text-xs">
      {stats.criticas > 0 && (
        <span className="bg-accent-red/20 text-accent-red px-1.5 py-0.5 rounded font-bold">
          {stats.criticas} críticas
        </span>
      )}
      {stats.altas > 0 && (
        <span className="bg-accent-yellow/20 text-accent-yellow px-1.5 py-0.5 rounded">
          {stats.altas} altas
        </span>
      )}
      <span className="text-slate-500">{total} total</span>
    </div>
  )
}

function NewsItem({ item }) {
  const [expanded, setExpanded] = useState(false)
  const p = PRIORITY_STYLE[item.priority] ?? PRIORITY_STYLE.BAJA
  const market = MARKET_LABEL[item.market] ?? item.market
  const hora = item.fetched_at ? item.fetched_at.slice(11, 16) : ''

  return (
    <div
      className="flex gap-3 py-2.5 border-b border-dark-600 last:border-0 cursor-pointer hover:bg-dark-700/50 px-2 rounded transition-colors"
      onClick={() => setExpanded(!expanded)}
    >
      {/* Priority dot */}
      <div className="pt-1.5 flex-shrink-0">
        <div className={`w-2 h-2 rounded-full ${p.dot}`} />
      </div>

      <div className="flex-1 min-w-0">
        {/* Title row */}
        <div className="flex items-start gap-2">
          <p className={`text-sm leading-snug flex-1 ${item.priority === 'CRITICA' ? 'text-white font-medium' : 'text-slate-300'}`}>
            {item.title}
          </p>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-2 mt-1">
          <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${p.badge}`}>
            {p.label}
          </span>
          <span className="text-xs text-slate-500">{market}</span>
          <span className="text-xs text-slate-600">{item.source}</span>
          <span className="text-xs text-slate-600 ml-auto">{hora}</span>
        </div>

        {/* Summary on expand */}
        {expanded && item.summary && (
          <p className="text-xs text-slate-400 mt-2 leading-relaxed border-l-2 border-dark-600 pl-2">
            {item.summary.slice(0, 300)}{item.summary.length > 300 ? '…' : ''}
          </p>
        )}
        {expanded && item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            onClick={e => e.stopPropagation()}
            className="text-xs text-accent-blue hover:underline mt-1 inline-block"
          >
            Leer fuente →
          </a>
        )}
      </div>
    </div>
  )
}

export default function NewsWidget() {
  const [priority, setPriority] = useState('')
  const [market,   setMarket]   = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [refreshMsg, setRefreshMsg] = useState(null)

  const endpoint = `/news?hours=24&limit=30${priority ? `&priority=${priority}` : ''}${market ? `&market=${market}` : ''}`
  const { data, loading, error, refetch, lastOk } = useApi(endpoint, 120000)
  const { data: stats } = useApi('/news/stats?hours=24', 120000)

  async function handleRefresh() {
    setRefreshing(true)
    setRefreshMsg(null)
    try {
      const res = await fetch('/api/news/refresh', { method: 'POST' })
      const d   = await res.json()
      setRefreshMsg(d.ok ? '✓ Actualizado' : `✗ ${d.stderr?.slice(0, 60) || 'Error'}`)
      if (d.ok) refetch()
    } catch {
      setRefreshMsg('✗ Sin conexión')
    } finally {
      setRefreshing(false)
      setTimeout(() => setRefreshMsg(null), 4000)
    }
  }

  const items = data?.items ?? []

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-600 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-white font-bold text-lg">📰 Noticias</h2>
          <StatsBar stats={stats} />
        </div>
        <div className="flex items-center gap-2">
          {lastOk && (
            <span className="text-xs text-slate-600">{lastOk.toLocaleTimeString('es-ES')}</span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-xs text-slate-500 hover:text-accent-blue transition-colors disabled:opacity-40"
          >
            {refreshing ? '⟳ Actualizando…' : '↻ Refresh'}
          </button>
          {refreshMsg && (
            <span className={`text-xs ${refreshMsg.startsWith('✓') ? 'text-accent-green' : 'text-accent-red'}`}>
              {refreshMsg}
            </span>
          )}
        </div>
      </div>

      {/* Filtros */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {/* Prioridad */}
        {['', 'CRITICA', 'ALTA', 'MEDIA', 'BAJA'].map(p => (
          <button
            key={p}
            onClick={() => setPriority(p)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
              priority === p
                ? 'bg-accent-blue/20 border-accent-blue text-accent-blue'
                : 'border-dark-600 text-slate-500 hover:border-slate-500'
            }`}
          >
            {p || 'Todas'}
          </button>
        ))}
        <div className="w-px bg-dark-600 mx-1" />
        {/* Mercado */}
        {['', 'iran', 'wti', 'macro'].map(m => (
          <button
            key={m}
            onClick={() => setMarket(m)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
              market === m
                ? 'bg-accent-blue/20 border-accent-blue text-accent-blue'
                : 'border-dark-600 text-slate-500 hover:border-slate-500'
            }`}
          >
            {m || 'Todos'}
          </button>
        ))}
      </div>

      {/* Lista */}
      {loading && (
        <div className="space-y-2">
          {[1,2,3,4].map(i => (
            <div key={i} className="h-10 bg-dark-700 rounded animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <p className="text-accent-red text-sm">Error: {error}</p>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="text-center py-8 text-slate-500 text-sm">
          Sin noticias para los filtros seleccionados.
          <br />
          <button onClick={handleRefresh} className="text-accent-blue hover:underline mt-2 inline-block">
            Cargar ahora →
          </button>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="max-h-80 overflow-y-auto -mx-2 px-2">
          {items.map(item => <NewsItem key={item.id} item={item} />)}
        </div>
      )}

      {items.length > 0 && (
        <div className="mt-3 pt-3 border-t border-dark-600 text-xs text-slate-600 text-center">
          {items.length} noticias · últimas 24h · haz clic en una para expandir
        </div>
      )}
    </div>
  )
}
