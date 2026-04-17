import { useEffect, useRef, useState } from 'react'
import type { Repository } from '../types'
import { api } from '../api'

interface Props {
  current: Repository | null
  onSelect: (repo: Repository) => void
  onNew: (repo: Repository) => void
}

export function RepoSwitcher({ current, onSelect, onNew }: Props) {
  const [open, setOpen] = useState(false)
  const [repos, setRepos] = useState<Repository[]>([])
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.listRepos().then(setRepos)
  }, [current]) // refresh list whenever current changes (new repo added)

  // Close on outside click
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
    try {
      const repo = await api.submitRepo(url.trim())
      setUrl('')
      setOpen(false)
      onNew(repo)
    } finally {
      setLoading(false)
    }
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
          {repos.length > 0 && (
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
          <form className="repo-new-form" onSubmit={handleSubmit}>
            <input
              type="url"
              placeholder="https://github.com/user/repo"
              value={url}
              onChange={e => setUrl(e.target.value)}
              autoFocus
            />
            <button type="submit" disabled={loading || !url.trim()}>
              {loading ? '…' : 'Analyze'}
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
