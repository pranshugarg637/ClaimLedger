import React, { useEffect, useState } from 'react'
import { ReviewAPI } from '../api/api.js'

export default function ReviewQueue() {
  const [claims, setClaims] = useState([])
  const [reason, setReason] = useState({})
  const [error, setError] = useState(null)
  const load = async () => {
    try { setClaims((await ReviewAPI.pending()).data); setError(null) }
    catch (e) { setError(e.response?.data?.detail || 'Verifier or admin role required.') }
  }
  useEffect(() => { load() }, [])
  const decide = async (id, decision) => {
    const reasoning = reason[id] || ''
    if (reasoning.length < 10) { setError('Enter a decision reason of at least 10 characters.'); return }
    await ReviewAPI.decide(id, { decision, reasoning })
    setClaims((items) => items.filter((c) => c.claim_id !== id))
  }
  return <div className="p-8 max-w-4xl">
    <header className="mb-8"><p className="mono-label">05 - Human decision</p><h1 className="font-display text-3xl font-semibold mt-1">Verifier Review Queue</h1><p className="text-ink/60 mt-1">Review-only claims require a documented human decision.</p></header>
    {error && <p className="text-rose-500 text-sm mb-4">{error}</p>}
    <div className="space-y-4">{claims.map((c) => <div className="card p-5" key={c.claim_id}>
      <p className="font-mono text-sm text-clinical-600">{c.claim_id}</p>
      <p className="text-sm mt-2">{c.patient_name} · {c.policy_number} · {c.procedure_code} · ₹{Number(c.claimed_amount).toLocaleString()}</p>
      <textarea value={reason[c.claim_id] || ''} onChange={(e) => setReason({...reason, [c.claim_id]: e.target.value})} placeholder="Explain the evidence behind your decision" className="mt-3 w-full border border-ink/15 rounded-md p-2 text-sm" rows="3" />
      <div className="flex gap-2 mt-3"><button onClick={() => decide(c.claim_id, 'approved')} className="px-3 py-2 rounded bg-clinical-600 text-white text-sm">Approve</button><button onClick={() => decide(c.claim_id, 'rejected')} className="px-3 py-2 rounded bg-rose-600 text-white text-sm">Reject</button></div>
    </div>)}</div>
    {!error && claims.length === 0 && <p className="text-ink/50">No claims are awaiting review.</p>}
  </div>
}
