import React, { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Landing from './components/Landing.jsx'
import AuthPage from './components/AuthPage.jsx'
import Portal from './components/Portal.jsx'
import { setRole, setUser as setApiUser } from './api/api.js'

export default function App() {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('claims_user') || 'null')
    } catch {
      return null
    }
  })

  useEffect(() => {
    setRole(user?.role)
    setApiUser(user?.username)
  }, [user])

  const handleLogout = () => {
    localStorage.removeItem('claims_user')
    setRole('')
    setApiUser('')
    setUser(null)
  }

  return (
    <>
      <Toaster position="top-right" />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth/:role" element={<AuthPage onLogin={setUser} />} />
          <Route path="/portal/*" element={user ? <Portal user={user} onLogout={handleLogout} /> : <Navigate to="/auth/patient" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </>
  )
}
