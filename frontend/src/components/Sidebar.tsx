import { useEffect, useState } from 'react'
import type { RepoFile, FileFn } from '../types'
import { api } from '../api'

interface TreeEntry {
  __type: 'file' | 'dir'
  __file?: RepoFile
  __children?: Record<string, TreeEntry>
}

function buildTree(files: RepoFile[]): Record<string, TreeEntry> {
  const root: Record<string, TreeEntry> = {}
  for (const f of files) {
    const parts = f.path.split('/')
    let node = root
    for (let i = 0; i < parts.length - 1; i++) {
      if (!node[parts[i]]) node[parts[i]] = { __type: 'dir', __children: {} }
      node = node[parts[i]].__children!
    }
    node[parts[parts.length - 1]] = { __type: 'file', __file: f }
  }
  return root
}

function sortEntries(entries: [string, TreeEntry][]) {
  return entries.sort(([, a], [, b]) => {
    if (a.__type === b.__type) return 0
    return a.__type === 'dir' ? -1 : 1
  })
}

interface TreeNodeProps {
  name: string
  node: TreeEntry
  depth: number
  path: string  // full path to this node
  selectedFile: RepoFile | null
  onSelect: (f: RepoFile) => void
  onSelectDir: (dir: string) => void
}

function TreeNode({ name, node, depth, path, selectedFile, onSelect, onSelectDir }: TreeNodeProps) {
  const [open, setOpen] = useState(depth < 2)
  const pl = 16 + depth * 14

  if (node.__type === 'file') {
    const selected = selectedFile?.id === node.__file!.id
    return (
      <div
        className={`tree-node ${selected ? 'selected' : ''}`}
        style={{ paddingLeft: pl }}
        onClick={() => onSelect(node.__file!)}
      >
        <span className="icon">📄</span>{name}
      </div>
    )
  }

  return (
    <>
      <div
        className="tree-node"
        style={{ paddingLeft: pl }}
        onClick={() => { setOpen(o => !o); onSelectDir(path) }}
      >
        <span className="icon">{open ? '▾' : '▸'}</span>{name}
      </div>
      {open && sortEntries(Object.entries(node.__children || {})).map(([k, v]) => (
        <TreeNode
          key={k} name={k} node={v} depth={depth + 1}
          path={path ? `${path}/${k}` : k}
          selectedFile={selectedFile} onSelect={onSelect} onSelectDir={onSelectDir}
        />
      ))}
    </>
  )
}

interface Props {
  repoId: string
  repoName: string
  selectedFile: RepoFile | null
  onSelectFile: (f: RepoFile) => void
  onSelectDir: (dir: string) => void
  onSelectFn: (fn: FileFn) => void
  onReanalyze: () => void
}

export function Sidebar({ repoId, repoName, selectedFile, onSelectFile, onSelectDir, onSelectFn, onReanalyze }: Props) {
  const [files, setFiles] = useState<RepoFile[]>([])
  const [functions, setFunctions] = useState<FileFn[]>([])

  useEffect(() => {
    api.getFileTree(repoId).then(setFiles)
  }, [repoId])

  useEffect(() => {
    if (!selectedFile) {
      setFunctions([])
      return
    }
    api.getFileFunctions(repoId, selectedFile.id).then(setFunctions)
  }, [selectedFile, repoId])

  const tree = buildTree(files)

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h3>{repoName}</h3>
        <button className="btn-reanalyze" onClick={onReanalyze}>↺ Re-analyze</button>
      </div>
      <div className="file-tree">
        {sortEntries(Object.entries(tree)).map(([k, v]) => (
          <TreeNode
            key={k} name={k} node={v} depth={0} path={k}
            selectedFile={selectedFile} onSelect={onSelectFile} onSelectDir={onSelectDir}
          />
        ))}
      </div>
      {functions.length > 0 && (
        <div className="fn-list">
          <h4>{selectedFile?.path.split('/').pop()}</h4>
          {functions.map(fn => (
            <div key={fn.id} className="fn-item" onClick={() => onSelectFn(fn)}>
              <span className="fn-name">{fn.name}()</span>
              <span className="fn-line">:{fn.start_line}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
