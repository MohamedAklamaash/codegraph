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

  return (
    <>
      {/* Persistent top-right switcher — visible on all views */}
      <div className="topbar">
        <RepoSwitcher current={repo} onSelect={handleSelect} onNew={handleSubmit} />
      </div>

      {view === 'landing' && <Landing onSubmit={handleSubmit} />}
      {view === 'processing' && <Processing repo={repo!} onReady={handleReady} />}
      {view === 'dashboard' && <Dashboard repo={repo!} onReanalyze={() => setView('processing')} />}
    </>
  )
}
