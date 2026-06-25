import { useRef, useState } from 'react'
import { Panel, PanelGroup, PanelResizeHandle, type ImperativePanelHandle } from 'react-resizable-panels'
import type { Repository, RepoFile } from '../types'
import { api } from '../api'
import { useChat } from '../hooks/useChat'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { Sidebar } from './Sidebar'
import { GraphPanel } from './GraphPanel'
import { ChatPanel } from './ChatPanel'
import { AskPalette } from './AskPalette'

interface Props {
  repo: Repository
  onReanalyze: () => void
  switcher: React.ReactNode
}

type MobileTab = 'files' | 'graph' | 'chat'

export function Dashboard({ repo, onReanalyze, switcher }: Props) {
  const [selectedFile, setSelectedFile] = useState<RepoFile | null>(null)
  const [selectedDir, setSelectedDir] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ id: string; n: number }>({ id: '', n: 0 })
  const [mobileTab, setMobileTab] = useState<MobileTab>('graph')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [chatOpen, setChatOpen] = useState(true)

  const sidebarRef = useRef<ImperativePanelHandle>(null)
  const chatRef = useRef<ImperativePanelHandle>(null)

  const isMobile = useMediaQuery('(max-width: 820px)')
  const { messages, streaming, send } = useChat(repo.id)

  const toggle = (panel: ImperativePanelHandle | null) => {
    if (!panel) return
    if (panel.isCollapsed()) panel.expand()
    else panel.collapse()
  }

  const handleReanalyze = async () => {
    await api.submitRepo(repo.url)
    onReanalyze()
  }

  const handleSelectFile = (f: RepoFile) => {
    setSelectedFile(f)
    setSelectedDir(null)
    if (isMobile) setMobileTab('graph')
  }

  const handleSelectDir = (dir: string) => {
    setSelectedDir(dir)
    setSelectedFile(null)
    if (isMobile) setMobileTab('graph')
  }

  const citeNode = (nodeId: string) => {
    setFocus(f => ({ id: nodeId, n: f.n + 1 }))
    if (isMobile) setMobileTab('graph')
  }

  const sidebar = (
    <Sidebar
      repoId={repo.id}
      repoName={repo.name}
      selectedFile={selectedFile}
      onSelectFile={handleSelectFile}
      onSelectDir={handleSelectDir}
      onSelectFn={() => {}}
      onReanalyze={handleReanalyze}
    />
  )

  const graph = (
    <GraphPanel
      repoId={repo.id}
      selectedFile={selectedFile}
      selectedDir={selectedDir}
      onNodeSelect={() => {}}
      focusNodeId={focus.id || null}
      focusNonce={focus.n}
    />
  )

  const chat = (
    <div className="right-panel">
      <div className="right-tabs">
        <span className="chat-header-title">Ask about the codebase</span>
      </div>
      <ChatPanel messages={messages} streaming={streaming} send={send} onCiteNode={citeNode} />
    </div>
  )

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div className="app-brand">
          {!isMobile && (
            <button
              className={`icon-btn ${sidebarOpen ? 'on' : ''}`}
              onClick={() => toggle(sidebarRef.current)}
              title={sidebarOpen ? 'Hide Explorer' : 'Show Explorer'}
              aria-label="Toggle Explorer"
            >
              <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="1.5" y="2.5" width="13" height="11" rx="2.5" />
                <line x1="6" y1="2.5" x2="6" y2="13.5" />
              </svg>
            </button>
          )}
          <svg className="app-logo" viewBox="0 0 24 24" width="20" height="20" aria-hidden>
            <circle cx="5" cy="6" r="2.4" fill="currentColor" />
            <circle cx="18" cy="5" r="2.4" fill="currentColor" opacity="0.55" />
            <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.8" />
            <path d="M6.7 7.4 L10.7 16.2 M15.8 6.4 L12.9 16" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.5" />
          </svg>
          <span className="app-brand-name" title={repo.name}>{repo.name}</span>
        </div>
        <div className="app-topbar-actions">
          {!isMobile && (
            <button
              className={`icon-btn ${chatOpen ? 'on' : ''}`}
              onClick={() => toggle(chatRef.current)}
              title={chatOpen ? 'Hide Chat' : 'Show Chat'}
              aria-label="Toggle Chat"
            >
              <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="1.5" y="2.5" width="13" height="11" rx="2.5" />
                <line x1="10" y1="2.5" x2="10" y2="13.5" />
              </svg>
            </button>
          )}
          {switcher}
        </div>
      </header>

      {isMobile ? (
        <>
          <div className="app-main mobile-pane">
            {mobileTab === 'files' && sidebar}
            {mobileTab === 'graph' && graph}
            {mobileTab === 'chat' && chat}
          </div>
          <nav className="mobile-tabbar">
            {(['files', 'graph', 'chat'] as MobileTab[]).map(t => (
              <button
                key={t}
                className={`mobile-tab ${mobileTab === t ? 'active' : ''}`}
                onClick={() => setMobileTab(t)}
              >
                {t === 'files' ? 'Files' : t === 'graph' ? 'Graph' : 'Chat'}
              </button>
            ))}
          </nav>
        </>
      ) : (
        <div className="app-main">
          <PanelGroup direction="horizontal" className="dashboard-panels" autoSaveId="codegraph-dashboard">
            <Panel
              ref={sidebarRef}
              collapsible
              collapsedSize={0}
              defaultSize={20}
              minSize={12}
              className="panel-col"
              onCollapse={() => setSidebarOpen(false)}
              onExpand={() => setSidebarOpen(true)}
            >
              {sidebar}
            </Panel>
            <PanelResizeHandle className="panel-resize-handle" />
            <Panel defaultSize={55} minSize={30} className="panel-col">{graph}</Panel>
            <PanelResizeHandle className="panel-resize-handle" />
            <Panel
              ref={chatRef}
              collapsible
              collapsedSize={0}
              defaultSize={25}
              minSize={18}
              className="panel-col"
              onCollapse={() => setChatOpen(false)}
              onExpand={() => setChatOpen(true)}
            >
              {chat}
            </Panel>
          </PanelGroup>
        </div>
      )}

      <AskPalette send={send} streaming={streaming} />
    </div>
  )
}
