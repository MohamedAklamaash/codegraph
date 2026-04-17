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
  const [selectedDir, setSelectedDir] = useState<string | null>(null)

  const handleReanalyze = async () => {
    await api.submitRepo(repo.url)
    onReanalyze()
  }

  const handleSelectFile = (f: RepoFile) => {
    setSelectedFile(f)
    setSelectedDir(null)
  }

  const handleSelectDir = (dir: string) => {
    setSelectedDir(dir)
    setSelectedFile(null)
  }

  return (
    <div className="dashboard">
      <Sidebar
        repoId={repo.id}
        repoName={repo.name}
        selectedFile={selectedFile}
        onSelectFile={handleSelectFile}
        onSelectDir={handleSelectDir}
        onSelectFn={() => {}}
        onReanalyze={handleReanalyze}
      />
      <GraphPanel
        repoId={repo.id}
        selectedFile={selectedFile}
        selectedDir={selectedDir}
        onNodeSelect={() => {}}
      />
      <div className="right-panel">
        <div className="right-tabs">
          <span className="chat-header-title">Ask about the codebase</span>
          {switcher}
        </div>
        <ChatPanel repoId={repo.id} onFocusFn={() => {}} switcher={null} />
      </div>
    </div>
  )
}
