import { useState } from 'react'
import type { Repository } from '../types'
import { api } from '../api'
import { GithubRepoPicker } from './GithubRepoPicker'

interface Props {
  onSubmit: (repo: Repository) => void
  switcher: React.ReactNode
}

type Tab = 'github' | 'url'

export function Landing({ onSubmit, switcher }: Props) {
  const [tab, setTab] = useState<Tab>('github')
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
      <h1>Code<span>Graph</span></h1>
      <p>Explore any GitHub repository as a function-level knowledge graph</p>

      <div className="landing-tabs">
        <button
          className={tab === 'github' ? 'active' : ''}
          onClick={() => setTab('github')}
        >
          Your GitHub
        </button>
        <button
          className={tab === 'url' ? 'active' : ''}
          onClick={() => setTab('url')}
        >
          By URL
        </button>
      </div>

      {tab === 'github' ? (
        <GithubRepoPicker onAnalyze={onSubmit} />
      ) : (
        <>
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
        </>
      )}
    </div>
  )
}
