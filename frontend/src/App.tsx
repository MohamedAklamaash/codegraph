import { useState } from 'react'
import type { Repository } from './types'
import { Landing } from './components/Landing'
import { Processing } from './components/Processing'
import { Dashboard } from './components/Dashboard'

type View = 'landing' | 'processing' | 'dashboard'

export default function App() {
  const [view, setView] = useState<View>('landing')
  const [repo, setRepo] = useState<Repository | null>(null)

  const handleSubmit = (r: Repository) => { setRepo(r); setView('processing') }
  const handleReady = (r: Repository) => { setRepo(r); setView('dashboard') }
  const handleReanalyze = () => setView('processing')

  if (view === 'landing') return <Landing onSubmit={handleSubmit} />
  if (view === 'processing') return <Processing repo={repo!} onReady={handleReady} />
  return <Dashboard repo={repo!} onReanalyze={handleReanalyze} />
}
