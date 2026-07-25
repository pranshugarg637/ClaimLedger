import React, { useState } from 'react'
import { UploadCloud, FileCheck2, Loader2 } from 'lucide-react'
import { ClaimsAPI } from '../api/api.js'
import { useNavigate } from 'react-router-dom'

export default function ClaimUpload({ user }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    patient_id: user?.role === 'patient' ? user.username : 'PAT-001',
    patient_name: user?.role === 'patient' ? user.username : 'Ravi Kumar',
    policy_number: 'POL-1001',
    hospital_id: 'HOSP-01',
    procedure_code: 'CARD-ANGIO',
    claimed_amount: 120000,
  })
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [uploadedClaimId, setUploadedClaimId] = useState(null)

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!file) { setError('Please attach a claim document (PDF, PNG, or JPG).'); return }
    setSubmitting(true)
    try {
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => fd.append(k, v))
      fd.append('document', file)
      const res = await ClaimsAPI.upload(fd)
      setUploadedClaimId(res.data.claim_id)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Check the backend is running.')
    } finally {
      setSubmitting(false)
    }
  }

  if (uploadedClaimId) {
    return (
      <div className="p-8 max-w-2xl">
        <div className="card p-8 text-center">
          <FileCheck2 className="w-10 h-10 text-clinical-600 mx-auto mb-3" strokeWidth={1.5} />
          <h2 className="font-display text-2xl">Claim submitted</h2>
          <p className="text-ink/60 mt-2 font-mono text-sm">{uploadedClaimId}</p>
          <p className="text-ink/60 mt-4">Head to Track Claim to run the agentic pipeline and watch it process live.</p>
          <div className="flex gap-3 justify-center mt-6">
            <button
              onClick={() => navigate(`/portal/track?claim_id=${uploadedClaimId}`)}
              className="px-4 py-2 bg-clinical-600 text-white rounded-lg text-sm font-medium hover:bg-clinical-700 transition-colors"
            >
              Track this claim
            </button>
            <button
              onClick={() => setUploadedClaimId(null)}
              className="px-4 py-2 border border-ink/15 rounded-lg text-sm font-medium hover:bg-ink/5 transition-colors"
            >
              Submit another
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-2xl">
      <header className="mb-8">
        <p className="mono-label">02 — Intake</p>
        <h1 className="font-display text-3xl font-semibold mt-1">Submit a Claim</h1>
        <p className="text-ink/60 mt-1">Attach the supporting document; the pipeline verifies everything downstream.</p>
      </header>

      <form onSubmit={handleSubmit} className="card p-6 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Patient ID" name="patient_id" value={form.patient_id} onChange={handleChange} />
          <Field label="Patient Name" name="patient_name" value={form.patient_name} onChange={handleChange} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Policy Number" name="policy_number" value={form.policy_number} onChange={handleChange} />
          <Field label="Hospital ID" name="hospital_id" value={form.hospital_id} onChange={handleChange} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Procedure Code" name="procedure_code" value={form.procedure_code} onChange={handleChange} />
          <Field label="Claimed Amount (₹)" name="claimed_amount" type="number" value={form.claimed_amount} onChange={handleChange} />
        </div>

        <div>
          <label className="mono-label block mb-1.5">Supporting Document</label>
          <label className="flex items-center gap-3 border border-dashed border-ink/20 rounded-lg px-4 py-6 cursor-pointer hover:border-clinical-500/50 hover:bg-clinical-50/40 transition-colors">
            <UploadCloud className="w-5 h-5 text-ink/40" strokeWidth={1.5} />
            <span className="text-sm text-ink/60">
              {file ? file.name : 'Click to choose a PDF, PNG, or JPG (max 10MB)'}
            </span>
            <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden"
              onChange={(e) => setFile(e.target.files[0])} />
          </label>
        </div>

        {error && <p className="text-rose-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 bg-clinical-600 text-white rounded-lg text-sm font-medium hover:bg-clinical-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          {submitting ? 'Uploading…' : 'Submit Claim'}
        </button>
      </form>
    </div>
  )
}

function Field({ label, name, value, onChange, type = 'text' }) {
  return (
    <div>
      <label className="mono-label block mb-1.5">{label}</label>
      <input
        type={type} name={name} value={value} onChange={onChange}
        className="w-full border border-ink/15 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-clinical-500/30"
      />
    </div>
  )
}
