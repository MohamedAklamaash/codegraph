import { useState } from 'react'
import { api } from '../api'

interface Props {
  repoId: string
  nodeId: string | null
  nodeName: string | null
}

export function TracePanel({ repoId, nodeId, nodeName }: Props) {
  const [trace, setTrace] = useState<{ name: string; file: string; start_line: number; trace: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [lastNodeId, setLastNodeId] = useState<string | null>(null)

  const load = async (id: string) => {
    setLoading(true)
    setTrace(null)
    try {
      const data = await api.traceNode(repoId, id)
      setTrace(data)
      setLastNodeId(id)
    } finally {
      setLoading(false)
    }
  }

  // Auto-load when nodeId changes
  if (nodeId && nodeId !== lastNodeId && !loading) {
    load(nodeId)
  }

  if (!nodeId) {
    return (
      <div className="trace-empty">
        Click a node in the graph to trace its flow.
      </div>
    )
  }

  return (
    <div className="trace-panel">
      {loading && (
        <div className="trace-loading">
          <span className="spinner" />
          Tracing {nodeName}…
        </div>
      )}
      {trace && !loading && (
        <>
          <div className="trace-header">
            <span className="trace-fn">{trace.name}()</span>
            <span className="trace-file">{trace.file}:{trace.start_line}</span>
          </div>
          <div className="trace-body">{trace.trace}</div>
        </>
      )}
    </div>
  )
}
