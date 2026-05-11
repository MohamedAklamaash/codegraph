import { useEffect, useState } from 'react'
import { api } from '../api'

export function Login() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('login_error') === '1') {
      setError('Sign in failed. Please try again.')
      params.delete('login_error')
      const next = params.toString()
      window.history.replaceState({}, '', window.location.pathname + (next ? `?${next}` : ''))
    }
  }, [])

  const handleClick = async () => {
    setLoading(true)
    setError('')
    try {
      await api.startGithubLogin()
    } catch {
      setError('Could not start GitHub sign-in. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="landing">
      <h1>CodeGraph</h1>
      <p>Sign in to explore your repositories as function-level knowledge graphs.</p>
      <button className="btn-primary" onClick={handleClick} disabled={loading}>
        {loading ? 'Redirecting…' : 'Sign in with GitHub'}
      </button>
      <p style={{ fontSize: 13, opacity: 0.7, marginTop: 12 }}>
        We request the <code>repo</code> scope so you can clone private repositories you choose.
      </p>
      {error && <p style={{ color: 'var(--error)', fontSize: 13 }}>{error}</p>}
    </div>
  )
}
