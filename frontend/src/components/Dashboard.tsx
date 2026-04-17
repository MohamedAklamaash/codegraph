import { useState } from 'react'
import type { Repository, RepoFile } from '../types'
import { api } from '../api'
import { Sidebar } from './Sidebar'
import { GraphPanel } from './GraphPanel'
import { ChatPanel } from './ChatPanel'

interface Props {
  repo: Repository
  onReanalyze: () => void
  switcher: React.ReactNode
}

export function Dashboard({ repo, onReanalyze, switcher }: Props) {
  const [selectedFile, setSelectedFile] = useState<RepoFile | null>(null)

  const handleReanalyze = async () => {
    await api.submitRepo(repo.url)
    onReanalyze()
  }

  return (
    <div className="dashboard">
      <Sidebar
        repoId={repo.id}
        repoName={repo.name}
        selectedFile={selectedFile}
        onSelectFile={setSelectedFile}
        onSelectFn={() => {}}
        onReanalyze={handleReanalyze}
      />
      <GraphPanel repoId={repo.id} selectedFile={selectedFile} />
      <ChatPanel repoId={repo.id} onFocusFn={() => {}} switcher={switcher} />
    </div>
  )
}
