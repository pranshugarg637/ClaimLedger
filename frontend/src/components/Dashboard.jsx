import React, { useEffect, useState } from 'react'
import { Activity, CheckCircle2, XCircle, AlertTriangle, Clock, IndianRupee } from 'lucide-react'
import { DashboardAPI, ClaimsAPI } from '../api/api.js'

const STATUS_STYLES = {
  approved: 'text-clinical-600 bg-clinical-50',
  rejected: 'text-rose-500 bg-rose-500/10',
  needs_review: 'text-amber-500 bg-amber-500/10',
  submitted: 'text-ink/50 bg-ink/5',
  processing: 'text-ink/50 bg-ink/5',
}

function StatCard({ icon: Icon, label, value, accent }) {
  return (
    <div className="card p-5 flex items-start justify-between">
      <div>
        <p className="mono-label">{label}</p>
        <p className="font-display text-3xl mt-1.5">{value}</p>
      </div>
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${accent}`}>
        <Icon className="w-4.5 h-4.5" strokeWidth={1.75} />
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    const [s, c] = await Promise.all([DashboardAPI.stats(), ClaimsAPI.list(15)])
    setStats(s.data)
    setClaims(c.data)
    setLoading(false)
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 8000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="p-8 max-w-6xl">
      <header className="mb-8">
        <p className="mono-label">01 — Overview</p>
        <h1 className="font-display text-3xl font-semibold mt-1">Claims Dashboard</h1>
        <p className="text-ink/60 mt-1">Live status across every claim moving through the agentic pipeline.</p>
      </header>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <StatCard icon={Activity} label="Total" value={stats.total_claims} accent="bg-ink/5 text-ink/60" />
          <StatCard icon={CheckCircle2} label="Approved" value={stats.approved} accent="bg-clinical-50 text-clinical-600" />
          <StatCard icon={XCircle} label="Rejected" value={stats.rejected} accent="bg-rose-500/10 text-rose-500" />
          <StatCard icon={AlertTriangle} label="Needs Review" value={stats.needs_review} accent="bg-amber-500/10 text-amber-500" />
          <StatCard icon={Clock} label="Pending" value={stats.pending} accent="bg-ink/5 text-ink/60" />
          <StatCard
            icon={IndianRupee}
            label="Total Claimed"
            value={`₹${(stats.total_claimed_amount / 1000).toFixed(0)}k`}
            accent="bg-ink/5 text-ink/60"
          />
        </div>
      )}

      <div className="card">
        <div className="px-5 py-4 border-b border-ink/10 flex items-center justify-between">
          <h2 className="font-display text-lg">Recent Claims</h2>
          <span className="mono-label">{claims.length} shown</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left mono-label border-b border-ink/10">
              <th className="px-5 py-2.5 font-medium">Claim ID</th>
              <th className="px-5 py-2.5 font-medium">Patient</th>
              <th className="px-5 py-2.5 font-medium">Procedure</th>
              <th className="px-5 py-2.5 font-medium">Amount</th>
              <th className="px-5 py-2.5 font-medium">Stage</th>
              <th className="px-5 py-2.5 font-medium">Decision</th>
              <th className="px-5 py-2.5 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {!loading && claims.length === 0 && (
              <tr><td colSpan={7} className="px-5 py-8 text-center text-ink/40">No claims submitted yet.</td></tr>
            )}
            {claims.map((c) => (
              <tr key={c.claim_id} className="border-b border-ink/5 hover:bg-ink/[0.02]">
                <td className="px-5 py-3 font-mono text-xs">{c.claim_id}</td>
                <td className="px-5 py-3">{c.patient_name}</td>
                <td className="px-5 py-3 text-ink/70">{c.procedure_code}</td>
                <td className="px-5 py-3 font-mono">₹{Number(c.claimed_amount).toLocaleString('en-IN')}</td>
                <td className="px-5 py-3 text-ink/60">{c.current_stage}</td>
                <td className="px-5 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[c.decision || c.status] || 'bg-ink/5 text-ink/50'}`}>
                    {c.decision || c.status}
                  </span>
                </td>
                <td className="px-5 py-3 font-mono text-ink/60">
                  {c.confidence_score != null ? `${(c.confidence_score * 100).toFixed(0)}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
