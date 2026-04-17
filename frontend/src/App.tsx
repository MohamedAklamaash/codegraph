import { useEffect, useState } from 'react'
import type { Repository } from './types'
import { api } from './api'
import { Landing } from './components/Landing'
import { Processing } from './components/Processing'
import { Dashboard } from './components/Dashboard'
import { RepoSwitcher } from './components/RepoSwitcher'

type View = 'landing' | 'processing' | 'dashboard'

const STORAGE_KEY = 'codegraph_last_repo_id'

export default function App() {
  const [view, setView] = useState<View>('landing')
  const [repo, setRepo] = useState<Repository | null>(null)
  const [restoring, setRestoring] = useState(true)

  // Restore last repo on mount
  useEffect(() => {
    const savedId = localStorage.getItem(STORAGE_KEY)
    if (!savedId) { setRestoring(false); return }
    api.getRepo(savedId)
      .then(r => {
        setRepo(r)
        setView(r.status === 'ready' ? 'dashboard' : 'processing')
      })
      .catch(() => localStorage.removeItem(STORAGE_KEY))
      .finally(() => setRestoring(false))
  }, [])

  const goTo = (r: Repository) => {
    setRepo(r)
    localStorage.setItem(STORAGE_KEY, r.id)
    setView(r.status === 'ready' ? 'dashboard' : 'processing')
  }

  const handleReady = (r: Repository) => {
    setRepo(r)
    localStorage.setItem(STORAGE_KEY, r.id)
    setView('dashboard')
  }

  if (restoring) return null

  const switcher = (
    <RepoSwitcher current={repo} onSelect={goTo} onNew={goTo} />
  )

  if (view === 'landing') return <Landing onSubmit={goTo} switcher={switcher} />
  if (view === 'processing') return <Processing repo={repo!} onReady={handleReady} switcher={switcher} />
  return <Dashboard repo={repo!} onReanalyze={() => setView('processing')} switcher={switcher} />
}
