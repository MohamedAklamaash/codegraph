import { useEffect, useState } from 'react'
import type { GitHubRepo, Repository } from '../types'
import { api } from '../api'

interface Props {
  onAnalyze: (repo: Repository) => void
}

function relativeTime(iso: string): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const sec = Math.floor((Date.now() - then) / 1000)
  if (sec < 60) return `${sec}s ago`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
  if (sec < 86400 * 30) return `${Math.floor(sec / 86400)}d ago`
  return new Date(iso).toLocaleDateString()
}

const Q_DEBOUNCE_MS = 300

export function GithubRepoPicker({ onAnalyze }: Props) {
  const [repos, setRepos] = useState<GitHubRepo[]>([])
  const [q, setQ] = useState('')
  // Debounced separately from `q` so each keystroke doesn't hit GitHub.
  const [debouncedQ, setDebouncedQ] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [needsReauth, setNeedsReauth] = useState(false)
  const [submittingId, setSubmittingId] = useState<number | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), Q_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    api.listMyGithubRepos(debouncedQ, page)
      .then(data => { if (!cancelled) setRepos(data) })
      .catch(err => {
        if (cancelled) return
        if (err?.response?.status === 401 && err?.response?.data?.needs_reauth) {
          setNeedsReauth(true)
        } else if (err?.response?.status === 503) {
          setError('GitHub rate limit reached. Try again shortly.')
        } else {
          setError('Could not load repositories.')
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [debouncedQ, page])

  const handleAnalyze = async (gh: GitHubRepo) => {
    setSubmittingId(gh.id)
    try {
      const repo = await api.submitRepo(gh.html_url)
      onAnalyze(repo)
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { error?: string } } }
      setError(e.response?.data?.error || 'Failed to submit repository')
    } finally {
      setSubmittingId(null)
    }
  }

  if (needsReauth) {
    return (
      <div className="gh-picker">
        <p>GitHub access expired — sign in again.</p>
        <button className="btn-primary" onClick={() => api.startGithubLogin()}>
          Sign in with GitHub
        </button>
      </div>
    )
  }

  return (
    <div className="gh-picker">
      <input
        type="text"
        placeholder="Filter by full name…"
        value={q}
        onChange={e => { setQ(e.target.value); setPage(1) }}
      />
      {loading && <p style={{ fontSize: 13, opacity: 0.7 }}>Loading…</p>}
      {error && <p style={{ color: 'var(--error)', fontSize: 13 }}>{error}</p>}
      {!loading && repos.length === 0 && !error && (
        <p style={{ fontSize: 13, opacity: 0.7 }}>No repositories found on this page.</p>
      )}
      <div className="gh-repo-list">
        {repos.map(r => (
          <div key={r.id} className="gh-repo-row">
            <div className="gh-repo-info">
              <span className="gh-repo-name" title={r.full_name}>{r.name}</span>
              {r.private && <span className="gh-repo-badge">Private</span>}
              <span className="gh-repo-time">{relativeTime(r.pushed_at)}</span>
            </div>
            <button
              className="btn-primary"
              onClick={() => handleAnalyze(r)}
              disabled={submittingId === r.id}
            >
              {submittingId === r.id ? '…' : 'Analyze'}
            </button>
          </div>
        ))}
      </div>
      <div className="gh-pager">
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1 || loading}>Prev</button>
        <span style={{ fontSize: 13, opacity: 0.7 }}>Page {page}</span>
        <button
          onClick={() => setPage(p => Math.min(10, p + 1))}
          disabled={loading || repos.length < 50}
        >
          Next
        </button>
      </div>
    </div>
  )
}
