import React, { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { DashboardAPI, ClaimsAPI } from '../api/api.js'

const COLORS = { approved: '#0E7C61', rejected: '#B5423A', needs_review: '#C2790B', pending: '#94a3b8' }

export default function Analytics({ user }) {
  const [stats, setStats] = useState(null)
  const [claims, setClaims] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const [s, c] = await Promise.all([DashboardAPI.stats(), ClaimsAPI.list(200)])
        if (!active) return
        setStats(s.data)
        setClaims(c.data)
        setError('')
      } catch (requestError) {
        if (active) setError(requestError.response?.data?.detail || 'Could not refresh claim analytics.')
      }
    }
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') load()
    }
    load()
    const interval = window.setInterval(load, 5000)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    return () => {
      active = false
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [user?.role, user?.username])

  if (!stats) return <div className="p-8">{error || 'Loading analytics...'}</div>

  const pieData = [
    { name: 'Approved', value: stats.approved, key: 'approved' },
    { name: 'Rejected', value: stats.rejected, key: 'rejected' },
    { name: 'Needs Review', value: stats.needs_review, key: 'needs_review' },
    { name: 'Pending', value: stats.pending, key: 'pending' },
  ].filter((d) => d.value > 0)

  const procedureCounts = {}
  claims.forEach((c) => {
    procedureCounts[c.procedure_code] = (procedureCounts[c.procedure_code] || 0) + 1
  })
  const barData = Object.entries(procedureCounts).map(([name, count]) => ({ name, count }))
  const sourceData = [
    { name: 'Direct approval', count: stats.direct_approved, fill: COLORS.approved },
    { name: 'Human approval', count: stats.human_approved, fill: '#2A9D8F' },
    { name: 'Direct rejection', count: stats.direct_rejected, fill: COLORS.rejected },
    { name: 'Human rejection', count: stats.human_rejected, fill: '#7F1D1D' },
  ].filter((item) => item.count > 0)
  const formatSource = (source) => ({ direct: 'Direct decision', human_review: 'Human review', pending: 'Pending' }[source] || source)

  return (
    <div className="p-8 max-w-5xl">
      <header className="mb-8">
        <p className="mono-label">05 — Analytics</p>
        <h1 className="font-display text-3xl font-semibold mt-1">{user?.role === 'patient' ? 'My Claims' : 'Portfolio Analytics'}</h1>
        <p className="text-ink/60 mt-1">{user?.role === 'patient' ? 'Every claim submitted from your patient account.' : 'Aggregate patterns across every claim the system has processed.'}</p>
        {error && <p className="text-rose-500 text-sm mt-3">{error}</p>}
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="card p-6">
          <p className="mono-label mb-4">Decision Distribution</p>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={3}>
                {pieData.map((entry) => <Cell key={entry.key} fill={COLORS[entry.key]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 justify-center mt-2">
            {pieData.map((d) => (
              <div key={d.key} className="flex items-center gap-1.5 text-xs text-ink/60">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[d.key] }} />
                {d.name} ({d.value})
              </div>
            ))}
          </div>
        </div>

        <div className="card p-6">
          <p className="mono-label mb-4">Claims by Procedure</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0F172A0D" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#0E7C61" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <p className="mono-label mb-4">Decision Source</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={sourceData} layout="vertical" margin={{ left: 12, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0F172A0D" />
              <XAxis type="number" allowDecimals={false} />
              <YAxis dataKey="name" type="category" width={105} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="count" name="Claims" radius={[0, 4, 4, 0]}>
                {sourceData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-6">
        <p className="mono-label mb-2">Average Model Confidence</p>
        <p className="font-display text-4xl">
          {stats.avg_confidence != null ? `${(stats.avg_confidence * 100).toFixed(1)}%` : '—'}
        </p>
        <p className="text-ink/50 text-sm mt-1">Blended across document, policy, medical, and fraud agents for all decided claims.</p>
      </div>

      <div className="card mt-6 overflow-x-auto">
        <div className="px-5 py-4 border-b border-ink/10 flex items-center justify-between">
          <div>
            <p className="mono-label">Claim register</p>
            <h2 className="font-display text-lg mt-1">All submitted claims</h2>
          </div>
          <span className="mono-label">{claims.length} shown</span>
        </div>
        <table className="w-full text-sm min-w-[900px]">
          <thead><tr className="text-left mono-label border-b border-ink/10">
            <th className="px-5 py-2.5 font-medium">Claim ID</th>
            {user?.role !== 'patient' && <th className="px-5 py-2.5 font-medium">Patient</th>}
            <th className="px-5 py-2.5 font-medium">Procedure</th><th className="px-5 py-2.5 font-medium">Amount</th>
            <th className="px-5 py-2.5 font-medium">Decision</th><th className="px-5 py-2.5 font-medium">Source</th>
            <th className="px-5 py-2.5 font-medium">Reviewed by</th><th className="px-5 py-2.5 font-medium">Submitted</th>
          </tr></thead>
          <tbody>
            {claims.length === 0 && <tr><td colSpan={user?.role === 'patient' ? 7 : 8} className="px-5 py-8 text-center text-ink/40">No claims submitted yet.</td></tr>}
            {claims.map((claim) => <tr key={claim.claim_id} className="border-b border-ink/5 hover:bg-ink/[0.02]">
              <td className="px-5 py-3 font-mono text-xs">{claim.claim_id}</td>
              {user?.role !== 'patient' && <td className="px-5 py-3">{claim.patient_name}<span className="block text-xs text-ink/40">{claim.patient_id}</span></td>}
              <td className="px-5 py-3 text-ink/70">{claim.procedure_code}</td><td className="px-5 py-3 font-mono">₹{Number(claim.claimed_amount).toLocaleString('en-IN')}</td>
              <td className="px-5 py-3 capitalize">{(claim.decision || claim.status || 'pending').replace('_', ' ')}</td><td className="px-5 py-3 text-ink/60">{formatSource(claim.decision_source)}</td>
              <td className="px-5 py-3 text-ink/60">{claim.reviewer || '—'}</td><td className="px-5 py-3 text-xs text-ink/50">{new Date(claim.created_at).toLocaleDateString()}</td>
            </tr>)}
          </tbody>
        </table>
      </div>
    </div>
  )
}
