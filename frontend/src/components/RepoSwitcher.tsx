import { useEffect, useRef, useState } from 'react'
import type { Repository } from '../types'
import { api } from '../api'
import { GithubRepoPicker } from './GithubRepoPicker'

interface Props {
  current: Repository | null
  onSelect: (repo: Repository) => void
  onNew: (repo: Repository) => void
}

type Mode = 'list' | 'github' | 'url'

export function RepoSwitcher({ current, onSelect, onNew }: Props) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<Mode>('list')
  const [repos, setRepos] = useState<Repository[]>([])
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.listRepos().then(setRepos).catch(() => setRepos([]))
  }, [current])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true)
    setError('')
    try {
      const repo = await api.submitRepo(url.trim())
      setUrl('')
      setOpen(false)
      setMode('list')
      onNew(repo)
    } catch (err: unknown) {
      // Surface backend-validation errors (invalid_url, needs_reauth,
      // no_access, github_unreachable) instead of swallowing them.
      const e2 = err as { response?: { status?: number; data?: { error?: string; detail?: string } } }
      const code = e2.response?.data?.error
      const detail = e2.response?.data?.detail
      if (code === 'invalid_url') {
        setError(detail ? `Invalid URL: ${detail}` : 'Invalid URL.')
      } else if (code === 'needs_reauth') {
        setError('GitHub session expired. Sign in again.')
      } else if (code === 'github_unreachable') {
        setError('Could not reach GitHub. Try again shortly.')
      } else if (code === 'no_access') {
        setError('No access to this repository.')
      } else if (code) {
        setError(code)
      } else {
        setError('Failed to submit repository.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handlePickerAnalyze = (repo: Repository) => {
    setOpen(false)
    setMode('list')
    onNew(repo)
  }

  const statusDot = (status: Repository['status']) => {
    if (status === 'ready') return '🟢'
    if (status === 'failed') return '🔴'
    return '🟡'
  }

  return (
    <div className="repo-switcher" ref={ref}>
      <button className="repo-switcher-btn" onClick={() => setOpen(o => !o)}>
        <span className="repo-switcher-name">
          {current ? current.name : 'Select repo'}
        </span>
        <span className="repo-switcher-caret">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="repo-switcher-dropdown">
          <div className="repo-switcher-tabs">
            <button className={mode === 'list' ? 'active' : ''} onClick={() => setMode('list')}>My repos</button>
            <button className={mode === 'github' ? 'active' : ''} onClick={() => setMode('github')}>From GitHub</button>
            <button className={mode === 'url' ? 'active' : ''} onClick={() => setMode('url')}>By URL</button>
          </div>

          {mode === 'list' && repos.length > 0 && (
            <div className="repo-list">
              {repos.map(r => (
                <div
                  key={r.id}
                  className={`repo-item ${current?.id === r.id ? 'active' : ''}`}
                  onClick={() => { onSelect(r); setOpen(false) }}
                >
                  <span className="repo-item-dot">{statusDot(r.status)}</span>
                  <span className="repo-item-name">{r.name}</span>
                  {r.status !== 'ready' && (
                    <span className="repo-item-status">{r.status}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {mode === 'list' && repos.length === 0 && (
            <p style={{ fontSize: 13, opacity: 0.7, padding: '8px 12px' }}>No repos yet.</p>
          )}

          {mode === 'github' && (
            <GithubRepoPicker onAnalyze={handlePickerAnalyze} />
          )}

          {mode === 'url' && (
            <form className="repo-new-form" onSubmit={handleSubmit}>
              <input
                type="url"
                placeholder="https://github.com/user/repo"
                value={url}
                onChange={e => { setUrl(e.target.value); setError('') }}
                autoFocus
              />
              <button type="submit" disabled={loading || !url.trim()}>
                {loading ? '…' : 'Analyze'}
              </button>
              {error && (
                <p style={{ color: 'var(--error)', fontSize: 13 }}>{error}</p>
              )}
            </form>
          )}
        </div>
      )}
    </div>
  )
}
