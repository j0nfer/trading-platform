import { useState, useEffect, useCallback } from 'react'

const BASE = '/api'

export function useApi(endpoint, intervalMs = 30000) {
  const [data, setData]       = useState(null)
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastOk, setLastOk]   = useState(null)

  const fetch_ = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}${endpoint}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
      setError(null)
      setLastOk(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [endpoint])

  useEffect(() => {
    fetch_()
    const id = setInterval(fetch_, intervalMs)
    return () => clearInterval(id)
  }, [fetch_, intervalMs])

  return { data, error, loading, lastOk, refetch: fetch_ }
}
