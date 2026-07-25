import React, { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { PolicyAPI } from '../api/api.js'

const initialForm = {
  policy_number: '', holder_name: '', patient_id: '', plan_type: '', coverage_limit: '',
  remaining_coverage: '', covered_procedures: '', status: 'active', start_date: '', end_date: '', policy_text: '',
}

function parseAmount(value) {
  const normalized = String(value).replace(/[₹,\s]/g, '')
  return normalized === '' ? NaN : Number(normalized)
}

export default function PolicyImport() {
  const [form, setForm] = useState(initialForm)
  const [message, setMessage] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setMessage(null)
    const coverageLimit = parseAmount(form.coverage_limit)
    const remainingCoverage = parseAmount(form.remaining_coverage)
    if (!Number.isFinite(coverageLimit) || coverageLimit <= 0) {
      setMessage({ type: 'error', text: 'Coverage limit must be a positive number, for example 500000 or 5,00,000.' })
      return
    }
    if (!Number.isFinite(remainingCoverage) || remainingCoverage < 0) {
      setMessage({ type: 'error', text: 'Remaining coverage must be zero or a valid number, for example 358000 or 3,58,000.' })
      return
    }
    setSubmitting(true)
    try {
      await PolicyAPI.import({
        ...form,
        coverage_limit: coverageLimit,
        remaining_coverage: remainingCoverage,
        covered_procedures: form.covered_procedures.split(',').map((item) => item.trim()).filter(Boolean),
      })
      setMessage({ type: 'success', text: 'Policy imported and indexed for local RAG.' })
      setForm(initialForm)
    } catch (error) {
      const detail = error.response?.data?.detail
      const text = Array.isArray(detail)
        ? detail.map((item) => `${item.loc?.at(-1) || 'field'}: ${item.msg}`).join('; ')
        : detail || 'Import failed. Check the backend connection and policy fields.'
      setMessage({ type: 'error', text })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-8 max-w-4xl">
      <header className="mb-8">
        <p className="mono-label">04 — Policy data</p>
        <h1 className="font-display text-3xl font-semibold mt-1">Import policy data</h1>
        <p className="text-ink/60 mt-2">Import authorised policy data and wording for policy verification.</p>
      </header>

      <form onSubmit={submit} className="card p-6 grid md:grid-cols-2 gap-4">
        {[
          ['policy_number', 'Policy number'], ['holder_name', 'Policy holder'], ['patient_id', 'Covered patient ID'],
          ['plan_type', 'Plan type'], ['coverage_limit', 'Coverage limit'], ['remaining_coverage', 'Remaining coverage'],
          ['covered_procedures', 'Procedures (comma-separated)'], ['start_date', 'Start date (YYYY-MM-DD)'], ['end_date', 'End date (YYYY-MM-DD)'],
        ].map(([name, label]) => (
          <label key={name} className="text-sm">
            {label}
            <input name={name} value={form[name]} onChange={update} required inputMode={name.includes('coverage') ? 'decimal' : undefined} className="mt-1 w-full border border-ink/15 rounded p-2" />
          </label>
        ))}
        <label className="text-sm">
          Status
          <select name="status" value={form.status} onChange={update} className="mt-1 w-full border border-ink/15 rounded p-2">
            <option value="active">Active</option><option value="expired">Expired</option><option value="suspended">Suspended</option>
          </select>
        </label>
        <label className="text-sm md:col-span-2">
          Policy wording for RAG
          <textarea name="policy_text" value={form.policy_text} onChange={update} className="mt-1 w-full border border-ink/15 rounded p-2" rows="6" placeholder="Paste authorised policy clauses, exclusions, waiting periods, and coverage conditions." />
        </label>
        {message && <p className={`md:col-span-2 text-sm ${message.type === 'error' ? 'text-rose-500' : 'text-clinical-600'}`}>{message.text}</p>}
        <button type="submit" disabled={submitting} className="md:col-span-2 inline-flex items-center justify-center gap-2 bg-clinical-600 text-white rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50">
          {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
          {submitting ? 'Importing...' : 'Import policy'}
        </button>
      </form>
    </div>
  )
}
