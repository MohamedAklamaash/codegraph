import { useEffect, useRef, useState } from 'react'
import type { Repository } from '../types'
import { api } from '../api'

const STEPS = [
  { key: 'cloning',   label: 'Cloning repo…' },
  { key: 'parsing',   label: 'Parsing files…' },
  { key: 'graphing',  label: 'Building graph…' },
  { key: 'embedding', label: 'Generating embeddings…' },
  { key: 'ready',     label: 'Done!' },
]

interface Props {
  repo: Repository
  onReady: (repo: Repository) => void
}

export function Processing({ repo: initial, onReady }: Props) {
  const [repo, setRepo] = useState(initial)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (repo.status === 'ready') { onReady(repo); return }
    if (repo.status === 'failed') return

    timer.current = setInterval(async () => {
      try {
        const updated = await api.getRepo(repo.id)
        setRepo(updated)
        if (updated.status === 'ready') { clearInterval(timer.current!); onReady(updated) }
        if (updated.status === 'failed') clearInterval(timer.current!)
      } catch {}
    }, 2000)

    return () => clearInterval(timer.current!)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo.id])

  const activeIdx = STEPS.findIndex(s => s.key === repo.status)

  return (
    <div className="processing">
      <h2>Analyzing {repo.name}</h2>
      <div className="steps">
        {STEPS.map((step, i) => {
          let cls = ''
          if (repo.status === 'failed' && i === activeIdx) cls = 'error'
          else if (i < activeIdx || repo.status === 'ready') cls = 'done'
          else if (i === activeIdx) cls = 'active'
          return (
            <div key={step.key} className={`step ${cls}`}>
              <span className="step-icon">
                {cls === 'done' ? '✓' : cls === 'error' ? '✗' : cls === 'active' ? <span className="spinner" /> : '○'}
              </span>
              {step.label}
            </div>
          )
        })}
      </div>
      {repo.status === 'failed' && (
        <p style={{ color: 'var(--error)', fontSize: 13 }}>{repo.status_message}</p>
      )}
    </div>
  )
}
