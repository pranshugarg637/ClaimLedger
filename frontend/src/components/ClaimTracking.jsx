import React, { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PlayCircle, FileText, ShieldQuestion, Stethoscope, Search, Gavel, Download, Loader2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'
import { ClaimsAPI, wsUrl } from '../api/api.js'

const STAGES = [
  { key: 'document_verification', label: 'Document Verification', icon: FileText },
  { key: 'policy_verification', label: 'Policy Verification', icon: ShieldQuestion },
  { key: 'medical_validation', label: 'Medical Validation', icon: Stethoscope },
  { key: 'fraud_detection', label: 'Fraud Detection', icon: Search },
  { key: 'decision', label: 'Decision', icon: Gavel },
]

const DECISION_META = {
  approved: { icon: CheckCircle2, color: 'text-clinical-600', bg: 'bg-clinical-50', label: 'Approved' },
  rejected: { icon: XCircle, color: 'text-rose-500', bg: 'bg-rose-500/10', label: 'Rejected' },
  needs_review: { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-500/10', label: 'Needs Human Review' },
}

export default function ClaimTracking() {
  const [params] = useSearchParams()
  const [claimId, setClaimId] = useState(params.get('claim_id') || '')
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState({})
  const [finalDecision, setFinalDecision] = useState(null)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => () => wsRef.current?.close(), [])

  const startProcessing = () => {
    if (!claimId) { setError('Enter a claim ID first.'); return }
    setError(null)
    setResults({})
    setFinalDecision(null)
    setRunning(true)

    const ws = new WebSocket(wsUrl(claimId))
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.error) { setError(data.error); setRunning(false); return }
      setResults((prev) => ({
        ...prev,
        document_verification: data.document_verification ?? prev.document_verification,
        policy_verification: data.policy_verification ?? prev.policy_verification,
        medical_validation: data.medical_validation ?? prev.medical_validation,
        fraud_detection: data.fraud_detection ?? prev.fraud_detection,
      }))
      if (data.final) {
        setFinalDecision({ decision: data.decision, confidence: data.confidence_score, reasoning: data.reasoning, reasonCodes: data.reason_codes || [], evidenceBundle: data.evidence_bundle })
        setRunning(false)
      }
    }
    ws.onerror = () => { setError('WebSocket connection failed. Is the backend running?'); setRunning(false) }
    ws.onclose = () => setRunning(false)
  }

  const downloadReport = async () => {
    const res = await ClaimsAPI.report(claimId)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `${claimId}_report.md`
    a.click()
  }

  const stageComplete = (key) => Boolean(results[key])
  const stageActive = (key, idx) => running && !stageComplete(key) &&
    STAGES.slice(0, idx).every((s) => s.key === 'decision' || stageComplete(s.key))

  return (
    <div className="p-8 max-w-4xl">
      <header className="mb-8">
        <p className="mono-label">03 — Live Processing</p>
        <h1 className="font-display text-3xl font-semibold mt-1">Track a Claim</h1>
        <p className="text-ink/60 mt-1">Watch each agent hand off state to the next in real time.</p>
      </header>

      <div className="card p-5 flex items-center gap-3 mb-8">
        <input
          value={claimId}
          onChange={(e) => setClaimId(e.target.value)}
          placeholder="CLM-XXXXXXXXXX"
          className="flex-1 border border-ink/15 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-clinical-500/30"
        />
        <button
          onClick={startProcessing}
          disabled={running}
          className="px-4 py-2 bg-clinical-600 text-white rounded-lg text-sm font-medium hover:bg-clinical-700 transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
          {running ? 'Processing…' : 'Run Agentic Workflow'}
        </button>
      </div>

      {error && <p className="text-rose-500 text-sm mb-6">{error}</p>}

      {/* Live pipeline rail */}
      <div className="card p-6 mb-6">
        <div className="relative flex justify-between">
          <div className="absolute top-5 left-5 right-5 h-px bg-ink/10" />
          {STAGES.map((s, idx) => {
            const done = s.key === 'decision' ? Boolean(finalDecision) : stageComplete(s.key)
            const active = s.key === 'decision' ? (running && Object.keys(results).length === 4) : stageActive(s.key, idx)
            const Icon = s.icon
            return (
              <div key={s.key} className="relative z-10 flex flex-col items-center w-1/5 text-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors
                  ${done ? 'bg-clinical-600 border-clinical-600 text-white rail-dot' :
                    active ? 'border-clinical-500 text-clinical-600 bg-white animate-pulse' :
                    'border-ink/15 text-ink/30 bg-white'}`}>
                  <Icon className="w-4.5 h-4.5" strokeWidth={1.75} />
                </div>
                <p className={`mt-2 text-xs font-medium leading-tight ${done ? 'text-ink' : 'text-ink/40'}`}>
                  {idx + 1}. {s.label}
                </p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Per-agent results */}
      <div className="space-y-3 mb-6">
        {STAGES.filter((s) => s.key !== 'decision').map((s) => {
          const r = results[s.key]
          if (!r) return null
          return (
            <div key={s.key} className="card p-4">
              <div className="flex items-center justify-between mb-1.5">
                <p className="font-medium text-sm">{s.label}</p>
                {r.confidence != null && (
                  <span className="mono-label">confidence {(r.confidence * 100).toFixed(0)}%</span>
                )}
              </div>
              <p className="text-sm text-ink/70">{r.summary}</p>
            </div>
          )
        })}
      </div>

      {/* Final decision */}
      {finalDecision && (() => {
        const meta = DECISION_META[finalDecision.decision] || DECISION_META.needs_review
        const Icon = meta.icon
        return (
          <div className={`card p-6 ${meta.bg}`}>
            <div className="flex items-center gap-3 mb-2">
              <Icon className={`w-6 h-6 ${meta.color}`} strokeWidth={1.75} />
              <h2 className={`font-display text-xl ${meta.color}`}>{meta.label}</h2>
              <span className="mono-label ml-auto">confidence {(finalDecision.confidence * 100).toFixed(0)}%</span>
            </div>
            <p className="text-sm text-ink/70 leading-relaxed">{finalDecision.reasoning}</p>
            {finalDecision.reasonCodes?.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink/60">Reason codes</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {finalDecision.reasonCodes.map((code) => (
                    <span key={code} className="px-2 py-1 rounded-full bg-white/70 text-xs font-mono">{code}</span>
                  ))}
                </div>
              </div>
            )}
            {finalDecision.evidenceBundle && (
              <details className="mt-3 text-sm text-ink/70">
                <summary className="cursor-pointer font-medium">Show evidence bundle</summary>
                <pre className="mt-2 whitespace-pre-wrap text-xs bg-white/70 p-3 rounded-md overflow-x-auto">{JSON.stringify(finalDecision.evidenceBundle, null, 2)}</pre>
              </details>
            )}
            <button
              onClick={downloadReport}
              className="mt-4 flex items-center gap-2 text-sm font-medium text-ink/70 hover:text-ink border border-ink/15 rounded-lg px-3 py-1.5 hover:bg-white transition-colors"
            >
              <Download className="w-4 h-4" /> Download claim report
            </button>
          </div>
        )
      })()}
    </div>
  )
}
