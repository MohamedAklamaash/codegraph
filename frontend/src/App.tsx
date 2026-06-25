import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import type { Repository } from './types'
import { api } from './api'
import { Landing } from './components/Landing'
import { Processing } from './components/Processing'
import { Dashboard } from './components/Dashboard'
import { RepoSwitcher } from './components/RepoSwitcher'
import { Login } from './components/Login'
import { ThemeToggle } from './components/ThemeToggle'
import { useAuth } from './auth/AuthContext'

const STORAGE_KEY = 'codegraph_last_repo_id'

function UserMenu() {
  const { user, logout } = useAuth()
  if (!user) return null
  return (
    <div className="user-menu">
      {user.avatar_url && (
        <img src={user.avatar_url} alt={user.login} className="user-avatar" />
      )}
      <span className="user-login">@{user.login}</span>
      <button className="user-logout" onClick={() => logout()}>Sign out</button>
    </div>
  )
}

// Topbar cluster reused across screens. Navigation is URL-driven now.
function Switcher({ current }: { current: Repository | null }) {
  const navigate = useNavigate()
  const goToRepo = (r: Repository) => navigate(`/r/${r.id}`)
  return (
    <div className="topbar-row">
      <RepoSwitcher current={current} onSelect={goToRepo} onNew={goToRepo} />
      <ThemeToggle />
      <UserMenu />
    </div>
  )
}

function Home() {
  const navigate = useNavigate()
  const savedId = localStorage.getItem(STORAGE_KEY)
  // Restore the last repo by redirecting to its URL; RepoView clears the key
  // and bounces back here if it no longer resolves (so this can't loop).
  if (savedId) return <Navigate to={`/r/${savedId}`} replace />
  return <Landing onSubmit={r => navigate(`/r/${r.id}`)} switcher={<Switcher current={null} />} />
}

function RepoView() {
  const { repoId } = useParams<{ repoId: string }>()
  const navigate = useNavigate()
  const [repo, setRepo] = useState<Repository | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!repoId) return
    setLoading(true)
    api.getRepo(repoId)
      .then(r => {
        setRepo(r)
        localStorage.setItem(STORAGE_KEY, r.id)
      })
      .catch(() => {
        localStorage.removeItem(STORAGE_KEY)
        navigate('/', { replace: true })
      })
      .finally(() => setLoading(false))
  }, [repoId, navigate])

  if (loading || !repo) return null

  const switcher = <Switcher current={repo} />

  if (repo.status === 'ready') {
    return (
      <Dashboard
        repo={repo}
        onReanalyze={() => api.getRepo(repo.id).then(setRepo)}
        switcher={switcher}
      />
    )
  }
  return <Processing repo={repo} onReady={setRepo} switcher={switcher} />
}

export default function App() {
  const { status } = useAuth()

  if (status === 'loading') return null
  if (status === 'anon') return <Login />

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/r/:repoId" element={<RepoView />} />
      {/* Reserved for Phase C (collaboration): */}
      {/* <Route path="/share/:token" element={<SharedRepo />} /> */}
      {/* <Route path="/orgs" element={<Orgs />} /> */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
