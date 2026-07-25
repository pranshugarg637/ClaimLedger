import React from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { UploadCloud, ListChecks, ScrollText, BarChart3, ShieldCheck, Database, Gavel } from 'lucide-react'
import Dashboard from './Dashboard.jsx'
import ClaimUpload from './ClaimUpload.jsx'
import ClaimTracking from './ClaimTracking.jsx'
import ReviewQueue from './ReviewQueue.jsx'
import PolicyImport from './PolicyImport.jsx'
import AuditLogs from './AuditLogs.jsx'
import Analytics from './Analytics.jsx'

const navItems = [
  { path: '/portal/upload', label: 'Submit claim', icon: UploadCloud, roles: ['patient', 'claims_officer'] },
  { path: '/portal/track', label: 'Track claim', icon: ListChecks, roles: ['patient', 'claims_officer'] },
  { path: '/portal/reviews', label: 'Review queue', icon: Gavel, roles: ['claims_officer', 'verifier', 'admin'] },
  { path: '/portal/policies', label: 'Import policies', icon: Database, roles: ['admin'] },
  { path: '/portal/audit', label: 'Audit trail', icon: ScrollText, roles: ['admin', 'auditor'] },
  { path: '/portal/analytics', label: 'Analytics', icon: BarChart3, roles: ['patient', 'admin', 'verifier', 'claims_officer'] },
]

const roleTitles = {
  patient: 'Patient portal',
  admin: 'Admin dashboard',
  verifier: 'Verifier workspace',
  claims_officer: 'Claims officer portal',
  auditor: 'Audit console',
}

function getDefaultPath(role) {
  if (role === 'admin') return '/portal/policies'
  if (role === 'verifier') return '/portal/reviews'
  if (role === 'auditor') return '/portal/audit'
  return '/portal/upload'
}

export default function Portal({ user, onLogout }) {
  const location = useLocation()
  const activeItems = navItems.filter((item) => item.roles.includes(user.role))

  const GuardedRoute = ({ allowedRoles, element }) =>
    allowedRoles.includes(user.role) ? element : <Navigate to={getDefaultPath(user.role)} replace />

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      <aside className="w-full max-w-xs border-r border-slate-200 bg-white p-6 hidden lg:flex flex-col">
        <div className="mb-8">
          <Link to="/portal" className="inline-flex items-center gap-3 text-xl font-semibold text-slate-900">
            <ShieldCheck className="w-6 h-6 text-teal-600" />
            ClaimSure
          </Link>
          <p className="mt-3 text-sm text-slate-500">{roleTitles[user.role] || 'Claim portal'}</p>
        </div>

        <nav className="space-y-2 flex-1">
          {activeItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-3xl px-4 py-3 text-sm font-medium transition ${
                    isActive ? 'bg-teal-700 text-white shadow' : 'text-slate-700 hover:bg-slate-100'
                  }`
                }
              >
                <Icon className="w-5 h-5" />
                {item.label}
              </NavLink>
            )
          })}
        </nav>

        <div className="mt-6 pt-6 border-t border-slate-200">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Signed in as</p>
          <p className="mt-2 font-semibold text-slate-900">{user.username}</p>
          <p className="text-xs text-slate-500 capitalize">{user.role}</p>
          <button onClick={onLogout} className="mt-5 w-full rounded-3xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 p-6 lg:p-8">
        {location.pathname === '/portal' && <Navigate to={getDefaultPath(user.role)} replace />}
        <Routes>
          <Route path="/" element={<Navigate to={getDefaultPath(user.role)} replace />} />
          <Route
            path="upload"
            element={<GuardedRoute allowedRoles={['patient', 'claims_officer']} element={<ClaimUpload user={user} />} />}
          />
          <Route
            path="track"
            element={<GuardedRoute allowedRoles={['patient', 'claims_officer']} element={<ClaimTracking />} />}
          />
          <Route
            path="reviews"
            element={<GuardedRoute allowedRoles={['claims_officer', 'verifier', 'admin']} element={<ReviewQueue />} />}
          />
          <Route
            path="policies"
            element={<GuardedRoute allowedRoles={['admin']} element={<PolicyImport />} />}
          />
          <Route
            path="audit"
            element={<GuardedRoute allowedRoles={['admin', 'auditor']} element={<AuditLogs />} />}
          />
          <Route
            path="analytics"
            element={<GuardedRoute allowedRoles={['patient', 'admin', 'verifier', 'claims_officer']} element={<Analytics user={user} />} />}
          />
          <Route path="*" element={<Navigate to={getDefaultPath(user.role)} replace />} />
        </Routes>
      </main>
    </div>
  )
}
