import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${BASE_URL}/api`,
})

const storedUser = JSON.parse(localStorage.getItem('claims_user') || 'null')
const storedRole = storedUser?.role || ''
api.defaults.headers.common['X-User-Role'] = storedRole
api.defaults.headers.common['X-User-Name'] = storedUser?.username || ''

export const AuthAPI = {
  signup: (payload) => api.post('/auth/signup', payload),
  login: (payload) => api.post('/auth/login', payload),
}

export function setRole(role) {
  if (role) {
    api.defaults.headers.common['X-User-Role'] = role
  } else {
    delete api.defaults.headers.common['X-User-Role']
  }
}

export function setUser(username) {
  if (username) {
    api.defaults.headers.common['X-User-Name'] = username
  } else {
    delete api.defaults.headers.common['X-User-Name']
  }
}

export const ClaimsAPI = {
  upload: (formData) =>
    api.post('/claims/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  process: (claimId) => api.post(`/claims/${claimId}/process`),
  getStatus: (claimId) => api.get(`/claims/${claimId}`),
  list: (limit = 100) => api.get(`/claims?limit=${limit}`),
  report: (claimId) => api.get(`/claims/${claimId}/report`, { responseType: 'blob' }),
}

export const PolicyAPI = {
  import: (payload) => api.post('/policies/import', payload),
}

export const AuditAPI = {
  forClaim: (claimId) => api.get(`/claims/${claimId}/audit-logs`),
  all: (limit = 200) => api.get(`/audit-logs?limit=${limit}`),
}

export const DashboardAPI = {
  stats: () => api.get('/dashboard/stats'),
}

export const ReviewAPI = {
  pending: () => api.get('/reviews/pending'),
  decide: (claimId, payload) => api.post(`/claims/${claimId}/review`, payload),
}

export function wsUrl(claimId) {
  const url = new URL(BASE_URL)
  const proto = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${url.host}/api/ws/claims/${claimId}/process`
}
