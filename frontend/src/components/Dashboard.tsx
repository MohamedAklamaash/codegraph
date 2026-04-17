import { useState } from 'react'
import type { Repository, RepoFile } from '../types'
import { api } from '../api'
import { Sidebar } from './Sidebar'
import { GraphPanel } from './GraphPanel'
import { ChatPanel } from './ChatPanel'
import { TracePanel } from './TracePanel'

type RightTab = 'chat' | 'trace'

interface Props {
  repo: Repository
  onReanalyze: () => void
  switcher: React.ReactNode
}

export function Dashboard({ repo, onReanalyze, switcher }: Props) {
  const [selectedFile, setSelectedFile] = useState<RepoFile | null>(null)
  const [rightTab, setRightTab] = useState<RightTab>('chat')
  const [traceNodeId, setTraceNodeId] = useState<string | null>(null)
  const [traceNodeName, setTraceNodeName] = useState<string | null>(null)

  const handleReanalyze = async () => {
    await api.submitRepo(repo.url)
    onReanalyze()
  }

  const handleNodeSelect = (id: string, name: string) => {
    setTraceNodeId(id)
    setTraceNodeName(name)
    setRightTab('trace')
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
      <GraphPanel
        repoId={repo.id}
        selectedFile={selectedFile}
        onNodeSelect={handleNodeSelect}
      />
      <div className="right-panel">
        <div className="right-tabs">
          <button
            className={`right-tab ${rightTab === 'chat' ? 'active' : ''}`}
            onClick={() => setRightTab('chat')}
          >
            Chat
          </button>
          <button
            className={`right-tab ${rightTab === 'trace' ? 'active' : ''}`}
            onClick={() => setRightTab('trace')}
          >
            Trace {traceNodeName ? `· ${traceNodeName}` : ''}
          </button>
          {rightTab === 'chat' && switcher}
        </div>
        {rightTab === 'chat' && (
          <ChatPanel repoId={repo.id} onFocusFn={() => {}} switcher={null} />
        )}
        {rightTab === 'trace' && (
          <TracePanel repoId={repo.id} nodeId={traceNodeId} nodeName={traceNodeName} />
        )}
      </div>
    </div>
  )
}
