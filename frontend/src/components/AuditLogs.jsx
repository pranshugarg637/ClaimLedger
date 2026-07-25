import React, { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { AuditAPI } from '../api/api.js'

export default function AuditLogs() {
  const [logs, setLogs] = useState([])
  const [filterClaim, setFilterClaim] = useState('')
  const [error, setError] = useState(null)

  const loadAll = async () => {
    try {
      const res = await AuditAPI.all(300)
      setLogs(res.data)
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load audit logs (auditor/admin role required).')
    }
  }

  const loadForClaim = async () => {
    if (!filterClaim) return loadAll()
    try {
      const res = await AuditAPI.forClaim(filterClaim)
      setLogs(res.data)
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load audit logs.')
    }
  }

  useEffect(() => { loadAll() }, [])

  return (
    <div className="p-8 max-w-5xl">
      <header className="mb-8">
        <p className="mono-label">04 — Governance</p>
        <h1 className="font-display text-3xl font-semibold mt-1">Audit Trail</h1>
        <p className="text-ink/60 mt-1">Immutable, per-agent record of every decision and why it was made.</p>
      </header>

      <div className="card p-4 flex items-center gap-3 mb-6">
        <input
          value={filterClaim}
          onChange={(e) => setFilterClaim(e.target.value)}
          placeholder="Filter by claim ID (optional)"
          className="flex-1 border border-ink/15 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-clinical-500/30"
        />
        <button
          onClick={loadForClaim}
          className="px-4 py-2 bg-ink/5 rounded-lg text-sm font-medium hover:bg-ink/10 transition-colors flex items-center gap-2"
        >
          <Search className="w-4 h-4" /> Filter
        </button>
      </div>

      {error && <p className="text-rose-500 text-sm mb-4">{error}</p>}

      <div className="space-y-3">
        {logs.length === 0 && !error && (
          <p className="text-ink/40 text-sm">No audit records yet — process a claim to generate one.</p>
        )}
        {logs.map((log) => (
          <div key={log.id} className="card p-4">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="mono-label text-clinical-600">{log.agent}</span>
                <span className="text-ink/30">→</span>
                <span className="text-sm font-medium">{log.action}</span>
              </div>
              <span className="mono-label">{new Date(log.timestamp).toLocaleString()}</span>
            </div>
            <p className="text-xs font-mono text-ink/40 mb-1">{log.claim_id}</p>
            <p className="text-sm text-ink/70">{log.reasoning}</p>
            {log.confidence != null && (
              <p className="mono-label mt-1.5">confidence {(log.confidence * 100).toFixed(0)}%</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
