import { useState } from 'react'
import type { Repository } from './types'
import { Landing } from './components/Landing'
import { Processing } from './components/Processing'
import { Dashboard } from './components/Dashboard'
import { RepoSwitcher } from './components/RepoSwitcher'

type View = 'landing' | 'processing' | 'dashboard'

export default function App() {
  const [view, setView] = useState<View>('landing')
  const [repo, setRepo] = useState<Repository | null>(null)

  const handleSubmit = (r: Repository) => {
    setRepo(r)
    setView(r.status === 'ready' ? 'dashboard' : 'processing')
  }

  const handleReady = (r: Repository) => { setRepo(r); setView('dashboard') }

  const handleSelect = (r: Repository) => {
    setRepo(r)
    setView(r.status === 'ready' ? 'dashboard' : 'processing')
  }

  const switcher = (
    <RepoSwitcher current={repo} onSelect={handleSelect} onNew={handleSubmit} />
  )

  if (view === 'landing') return <Landing onSubmit={handleSubmit} switcher={switcher} />
  if (view === 'processing') return <Processing repo={repo!} onReady={handleReady} switcher={switcher} />
  return <Dashboard repo={repo!} onReanalyze={() => setView('processing')} switcher={switcher} />
}
