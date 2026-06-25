import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import type { Repository } from '../types'
import { api } from '../api'
import { REPO_STATUSES } from '../constants/repoStatus'

const DONE_HOLD_MS = 600

interface Props {
  repo: Repository
  onReady: (repo: Repository) => void
  switcher: React.ReactNode
}

export function Processing({ repo: initial, onReady, switcher }: Props) {
  const [repo, setRepo] = useState(initial)
  const [readyHolding, setReadyHolding] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const retry = async () => {
    setRetrying(true)
    try {
      setRepo(await api.submitRepo(repo.url))
    } catch {
      /* keep the failed state; the user can retry again */
    } finally {
      setRetrying(false)
    }
  }

  useEffect(() => {
    if (repo.status === 'failed') return

    if (repo.status === 'ready') {
      setReadyHolding(true)
      const t = setTimeout(() => onReady(repo), DONE_HOLD_MS)
      return () => clearTimeout(t)
    }

    timer.current = setInterval(async () => {
      try {
        const updated = await api.getRepo(repo.id)
        setRepo(updated)
        if (updated.status === 'failed') clearInterval(timer.current!)
        if (updated.status === 'ready') clearInterval(timer.current!)
      } catch {}
    }, 2000)

    return () => clearInterval(timer.current!)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo.id, repo.status])

  const activeIdx = repo.status === 'pending'
    ? 0
    : REPO_STATUSES.findIndex(s => s.key === repo.status)

  return (
    <div className="processing">
      <div className="landing-topbar">{switcher}</div>
      <h2>Analyzing {repo.name}</h2>
      <div className="steps">
        {REPO_STATUSES.map((step, i) => {
          let cls = ''
          if (repo.status === 'failed' && i === activeIdx) cls = 'error'
          else if (i < activeIdx || repo.status === 'ready') cls = 'done'
          else if (i === 0 && (repo.status === 'pending' || repo.status === 'cloning')) cls = 'active'
          else if (i === activeIdx) cls = 'active'
          return (
            <motion.div
              key={step.key}
              className={`step ${cls}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.07, ease: 'easeOut' }}
            >
              <span className="step-icon">
                {cls === 'done' ? '✓' : cls === 'error' ? '✗' : cls === 'active' ? <span className="spinner" /> : '○'}
              </span>
              <div className="step-body">
                <div className="step-label">{step.label}</div>
                <div className="step-description">{step.description}</div>
              </div>
            </motion.div>
          )
        })}
      </div>
      {readyHolding && (
        <p style={{ color: 'var(--success)', fontSize: 13 }}>Done — opening dashboard…</p>
      )}
      {repo.status === 'failed' && (
        <div className="processing-failed">
          <p className="processing-error">{repo.status_message}</p>
          <button className="btn-retry" onClick={retry} disabled={retrying}>
            {retrying ? 'Retrying…' : 'Retry — pull latest & re-analyze'}
          </button>
        </div>
      )}
    </div>
  )
}
