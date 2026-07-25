import React from 'react'
import { Link } from 'react-router-dom'
import { ShieldCheck, BadgeCheck, FileSearch, HeartPulse, Sparkles } from 'lucide-react'

export default function Landing() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link to="/" className="inline-flex items-center gap-3 text-xl font-semibold text-slate-900">
            <ShieldCheck className="w-6 h-6 text-teal-700" />
            ClaimSure
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-sm text-slate-600">
            <Link to="/auth/patient" className="hover:text-slate-900">Patient</Link>
            <Link to="/auth/admin" className="hover:text-slate-900">Admin</Link>
            <Link to="/auth/verifier" className="hover:text-slate-900">Verifier</Link>
            <Link to="/auth/patient" className="rounded-full bg-teal-700 px-4 py-2 text-white transition hover:bg-teal-800">Sign in</Link>
          </nav>
        </div>
      </header>

      <main className="space-y-24">
        <section className="mx-auto max-w-7xl px-6 py-20 lg:grid lg:grid-cols-2 lg:items-center lg:gap-16">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full bg-teal-100 px-4 py-2 text-sm font-semibold text-teal-700">
              <Sparkles className="w-4 h-4" /> Trusted by modern insurers
            </span>
            <h1 className="mt-8 text-5xl font-semibold tracking-tight text-slate-900 sm:text-6xl">
              Insurance claim processing with a premium customer experience.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-slate-600">
              ClaimSure brings fast claim submission, policy validation, and role-based dashboards together in a polished product designed for patients, reviewers, and administrators.
            </p>
            <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link to="/auth/patient" className="inline-flex items-center justify-center rounded-3xl bg-teal-700 px-6 py-3 text-sm font-semibold text-white transition hover:bg-teal-800">
                Get started
              </Link>
              <Link to="/auth/admin" className="inline-flex items-center justify-center rounded-3xl border border-slate-200 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
                Admin access
              </Link>
            </div>
          </div>

          <div className="mt-12 lg:mt-0">
            <div className="rounded-[2rem] bg-gradient-to-br from-teal-700 via-cyan-600 to-slate-900 p-8 text-white shadow-2xl">
              <div className="rounded-[1.75rem] bg-white/10 p-6 backdrop-blur-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm uppercase tracking-[0.2em] text-teal-200">Live claim visibility</p>
                    <p className="mt-4 text-3xl font-semibold">Track every step</p>
                  </div>
                  <span className="rounded-full bg-white/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-100">Secure</span>
                </div>
                <div className="mt-8 grid gap-4 text-sm text-slate-200">
                  <div className="rounded-3xl bg-white/10 p-4">
                    <p className="font-semibold">Policy verification</p>
                    <p className="mt-2 text-slate-200/80">Built-in coverage and member checks for every claim.</p>
                  </div>
                  <div className="rounded-3xl bg-white/10 p-4">
                    <p className="font-semibold">Role-based portals</p>
                    <p className="mt-2 text-slate-200/80">Patients, admins, and verifiers each get the right tools.</p>
                  </div>
                  <div className="rounded-3xl bg-white/10 p-4">
                    <p className="font-semibold">Audit-ready operations</p>
                    <p className="mt-2 text-slate-200/80">Every decision saved with transparency and data lineage.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="bg-white py-20">
          <div className="mx-auto max-w-6xl px-6">
            <div className="text-center">
              <p className="text-sm uppercase tracking-[0.3em] text-teal-700">How it works</p>
              <h2 className="mt-4 text-3xl font-semibold text-slate-900">Streamlined for every insurance role.</h2>
              <p className="mt-4 mx-auto max-w-2xl text-base leading-8 text-slate-600">
                ClaimSure makes it easy to submit documents, validate coverage, and keep an audit trail without confusing screens or scattered systems.
              </p>
            </div>
            <div className="mt-14 grid gap-6 md:grid-cols-3">
              {[
                { icon: FileSearch, title: 'Submit claims', text: 'Patients upload documents and policy details from one modern portal.' },
                { icon: BadgeCheck, title: 'Validate policies', text: 'Automated checks match policy terms and claim requirements.' },
                { icon: HeartPulse, title: 'Review confidently', text: 'Verifiers and admins review flagged claims with full evidence.' },
              ].map((item) => (
                <div key={item.title} className="rounded-3xl border border-slate-200 bg-slate-50 p-8 shadow-sm">
                  <item.icon className="h-8 w-8 text-teal-700" />
                  <h3 className="mt-6 text-xl font-semibold text-slate-900">{item.title}</h3>
                  <p className="mt-3 text-slate-600">{item.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
