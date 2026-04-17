import { useEffect, useState } from 'react'
import { api } from '../api'

interface FlowStep {
  id: string
  name: string
  file: string
  depth: number
  parent_id: string | null
}

interface TraceData {
  name: string
  file: string
  start_line: number
  flow: FlowStep[]
  explanation: string
}

interface Props {
  repoId: string
  nodeId: string | null
  nodeName: string | null
}

export function TracePanel({ repoId, nodeId, nodeName }: Props) {
  const [data, setData] = useState<TraceData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!nodeId) return
    setData(null)
    setLoading(true)
    api.traceNode(repoId, nodeId).then(setData).finally(() => setLoading(false))
  }, [repoId, nodeId])

  if (!nodeId) {
    return <div className="trace-empty">Click a node in the graph to trace its full execution flow.</div>
  }

  if (loading) {
    return (
      <div className="trace-empty">
        <span className="spinner" style={{ display: 'inline-block', marginRight: 8 }} />
        Tracing {nodeName}…
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="trace-panel">
      <div className="trace-fn-header">
        <span className="trace-fn-label">Function</span>
        <span className="trace-fn-name">{data.name}()</span>
        <span className="trace-fn-file">{data.file}:{data.start_line}</span>
      </div>

      <div className="trace-section">
        <div className="trace-section-title">
          Flow {data.flow.length > 0 && <span className="trace-count">{data.flow.length} steps</span>}
        </div>
        {data.flow.length === 0 ? (
          <div className="trace-no-flow">No outgoing calls detected.</div>
        ) : (
          <div className="trace-steps">
            {data.flow.map((step, i) => (
              <div
                key={step.id + i}
                className="trace-step"
                style={{ paddingLeft: 10 + (step.depth - 1) * 20 }}
              >
                <span className="trace-step-depth" title={`depth ${step.depth}`}>
                  {step.depth > 1 ? '└' : ''}
                </span>
                <span className="trace-step-arrow">→</span>
                <span className="trace-step-name">{step.name}</span>
                <span className="trace-step-file">{step.file.split('/').pop()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="trace-section">
        <div className="trace-section-title">Explanation</div>
        <div className="trace-explanation">{data.explanation}</div>
      </div>
    </div>
  )
}
