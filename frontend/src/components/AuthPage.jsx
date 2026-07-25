import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ShieldCheck, User, Key, Lock, Shield } from 'lucide-react'
import toast from 'react-hot-toast'
import { AuthAPI, setRole } from '../api/api.js'

const roleLabels = {
  patient: 'Patient',
  admin: 'Admin',
  verifier: 'Verifier',
  claims_officer: 'Claims officer',
  auditor: 'Auditor',
}

const roleRedirect = {
  patient: '/portal/upload',
  admin: '/portal/policies',
  verifier: '/portal/reviews',
  claims_officer: '/portal/reviews',
  auditor: '/portal/audit',
}

export default function AuthPage({ onLogin }) {
  const { role = 'patient' } = useParams()
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setMode('login')
    setForm({ username: '', password: '' })
  }, [role])

  const nextPath = roleRedirect[role] || '/portal'

  const submit = async (event) => {
    event.preventDefault()
    if (!form.username || !form.password) {
      toast.error('Enter both username and password.')
      return
    }

    setLoading(true)
    try {
      const response = await AuthAPI[mode]({ ...form, role })
      const user = response.data
      setRole(user.role)
      localStorage.setItem('claims_user', JSON.stringify(user))
      toast.success(`${mode === 'login' ? 'Welcome back' : 'Account created'} — ${user.username}`)
      onLogin(user)
      navigate(roleRedirect[user.role] || '/portal', { replace: true })
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Unable to continue.'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <div className="mx-auto w-full max-w-6xl px-6 py-8 flex items-center justify-between">
        <Link to="/" className="inline-flex items-center gap-3 text-lg font-semibold text-slate-900">
          <ShieldCheck className="w-6 h-6 text-teal-700" />
          ClaimSure
        </Link>
        <div className="flex items-center gap-3 text-sm text-slate-600">
          <Link to="/auth/patient" className={role === 'patient' ? 'font-semibold text-slate-900' : 'hover:text-slate-900'}>Patient</Link>
          <Link to="/auth/admin" className={role === 'admin' ? 'font-semibold text-slate-900' : 'hover:text-slate-900'}>Admin</Link>
          <Link to="/auth/verifier" className={role === 'verifier' ? 'font-semibold text-slate-900' : 'hover:text-slate-900'}>Verifier</Link>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-10 flex-1 px-6 pb-12">
        <section className="hidden lg:flex flex-col justify-center rounded-[2rem] bg-gradient-to-br from-teal-900 via-slate-900 to-slate-700 p-12 text-white shadow-2xl">
          <p className="text-sm uppercase tracking-[0.3em] text-teal-200">Secure insurance experience</p>
          <h1 className="mt-6 text-5xl font-semibold leading-tight">Fast access for every role.</h1>
          <p className="mt-5 text-slate-200 text-lg max-w-xl">Patients, analysts, and admins all sign in from one strong portal. Authentication unlocks the right claim tools for your work.</p>

          <div className="mt-10 grid gap-4">
            {[
              { label: 'Patient', text: 'Submit and track claims with clear status updates.', icon: User },
              { label: 'Admin', text: 'Import policies, review workflows, and manage access.', icon: Shield },
              { label: 'Verifier', text: 'Review flagged claims with full evidence context.', icon: Lock },
            ].map((item) => (
              <div key={item.label} className="rounded-3xl bg-white/10 p-5">
                <div className="inline-flex items-center gap-3 text-sm uppercase tracking-[0.25em] text-teal-200">
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </div>
                <p className="mt-3 text-slate-100">{item.text}</p>
              </div>
            ))}
          </div>
        </section>

        <main className="flex items-center justify-center">
          <form onSubmit={submit} className="w-full max-w-md rounded-[2rem] bg-white border border-slate-200 p-8 shadow-xl">
            <div className="flex items-center justify-between gap-4 mb-8">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-teal-700">{roleLabels[role] || 'Patient'} access</p>
                <h2 className="mt-3 text-3xl font-semibold">{mode === 'login' ? 'Sign in to your account' : 'Create your account'}</h2>
              </div>
              <div className="inline-flex items-center justify-center rounded-3xl bg-slate-100 p-3 text-slate-500">
                <ShieldCheck className="w-6 h-6 text-teal-700" />
              </div>
            </div>

            <div className="flex gap-2 rounded-full bg-slate-100 p-1 text-sm font-medium text-slate-600 mb-6">
              <button type="button" onClick={() => setMode('login')} className={`flex-1 rounded-full px-4 py-2 transition ${mode === 'login' ? 'bg-white shadow-sm text-slate-900' : 'hover:text-slate-900'}`}>
                Login
              </button>
              <button type="button" onClick={() => setMode('signup')} className={`flex-1 rounded-full px-4 py-2 transition ${mode === 'signup' ? 'bg-white shadow-sm text-slate-900' : 'hover:text-slate-900'}`}>
                Sign up
              </button>
            </div>

            <label className="block text-sm font-medium text-slate-700">Username</label>
            <input
              type="text"
              value={form.username}
              onChange={(event) => setForm({ ...form, username: event.target.value })}
              className="mt-2 w-full rounded-3xl border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300"
              placeholder="Enter your username"
            />

            <label className="mt-5 block text-sm font-medium text-slate-700">Password</label>
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              className="mt-2 w-full rounded-3xl border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300"
              placeholder="Enter your password"
            />

            <button
              type="submit"
              disabled={loading}
              className="mt-8 w-full rounded-3xl bg-teal-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loading ? 'Working…' : mode === 'login' ? 'Login now' : 'Create account'}
            </button>

            <div className="mt-6 text-center text-sm text-slate-500">
              {mode === 'login' ? (
                <span>
                  New here?{' '}
                  <button type="button" onClick={() => setMode('signup')} className="font-semibold text-slate-900 hover:text-teal-700">
                    Create account
                  </button>
                </span>
              ) : (
                <span>
                  Already have an account?{' '}
                  <button type="button" onClick={() => setMode('login')} className="font-semibold text-slate-900 hover:text-teal-700">
                    Sign in
                  </button>
                </span>
              )}
            </div>

            <div className="mt-8 border-t border-slate-200 pt-6 text-sm text-slate-500">
              <p className="mb-3">Choose another role:</p>
              <div className="grid grid-cols-3 gap-2">
                <Link to="/auth/patient" className="rounded-3xl border border-slate-200 bg-slate-50 px-3 py-2 text-center text-xs font-semibold text-slate-700 hover:bg-slate-100">Patient</Link>
                <Link to="/auth/admin" className="rounded-3xl border border-slate-200 bg-slate-50 px-3 py-2 text-center text-xs font-semibold text-slate-700 hover:bg-slate-100">Admin</Link>
                <Link to="/auth/verifier" className="rounded-3xl border border-slate-200 bg-slate-50 px-3 py-2 text-center text-xs font-semibold text-slate-700 hover:bg-slate-100">Verifier</Link>
              </div>
            </div>

            <div className="mt-6 flex items-center gap-2 text-xs text-slate-400">
              <Key className="w-4 h-4" />
              <span>Role-based login ensures the right portal opens after authentication.</span>
            </div>
          </form>
        </main>
      </div>
    </div>
  )
}
