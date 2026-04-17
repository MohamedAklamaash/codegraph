import { useState } from 'react'
import type { Repository } from '../types'
import { api } from '../api'

interface Props {
  onSubmit: (repo: Repository) => void
  switcher: React.ReactNode
}

export function Landing({ onSubmit, switcher }: Props) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true)
    setError('')
    try {
      const repo = await api.submitRepo(url.trim())
      onSubmit(repo)
    } catch (err: unknown) {
      setError((err as { response?: { data?: { error?: string } } }).response?.data?.error || 'Failed to submit repository')
      setLoading(false)
    }
  }

  return (
    <div className="landing">
      <div className="landing-topbar">{switcher}</div>
      <h1>CodeGraph</h1>
      <p>Explore any GitHub repository as a function-level knowledge graph</p>
      <form className="url-form" onSubmit={handleSubmit}>
        <input
          type="url"
          placeholder="https://github.com/user/repo"
          value={url}
          onChange={e => setUrl(e.target.value)}
          required
        />
        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? 'Submitting…' : 'Analyze'}
        </button>
      </form>
      {error && <p style={{ color: 'var(--error)', fontSize: 13 }}>{error}</p>}
    </div>
  )
}
