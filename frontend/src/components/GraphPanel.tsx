import { useCallback, useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { RepoFile, FunctionNode, FunctionEdge } from '../types'
import { api } from '../api'
import { TracePanel } from './TracePanel'

type GraphMode = 'full' | 'file' | 'flow'

interface NodeDatum extends d3.SimulationNodeDatum {
  id: string
  name: string
  file: string
  file_id: number
  start_line: number
  summary: string
  isExternal: boolean
}

interface EdgeDatum extends d3.SimulationLinkDatum<NodeDatum> {
  id: string
  type: string
}

interface SelectedNode {
  node: NodeDatum
  deps: { id: string; name: string; file: string; direction: 'calls' | 'called-by' }[]
}

interface Props {
  repoId: string
  selectedFile: RepoFile | null
  onNodeSelect: (id: string, name: string) => void
}

const FILE_COLORS = [
  '#58a6ff', '#3fb950', '#d29922', '#a371f7',
  '#f78166', '#39d353', '#79c0ff', '#ffa657',
]

export function GraphPanel({ repoId, selectedFile, onNodeSelect }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simRef = useRef<d3.Simulation<NodeDatum, EdgeDatum> | null>(null)
  const [mode, setMode] = useState<GraphMode>('full')
  const [selected, setSelected] = useState<SelectedNode | null>(null)
  const [nodeCount, setNodeCount] = useState(0)
  const [traceNodeId, setTraceNodeId] = useState<string | null>(null)
  const [traceNodeName, setTraceNodeName] = useState<string | null>(null)

  const draw = useCallback(async (m: GraphMode) => {
    const svg = svgRef.current
    if (!svg || m === 'flow') return

    const params: { file_id?: number } = {}
    if (m === 'file' && selectedFile) params.file_id = selectedFile.id

    let rawNodes: FunctionNode[], rawEdges: FunctionEdge[]
    try {
      const data = await api.getGraph(repoId, params)
      rawNodes = data.nodes
      rawEdges = data.edges
    } catch { return }

    setNodeCount(rawNodes.length)

    simRef.current?.stop()
    d3.select(svg).selectAll('*').remove()

    const W = svg.clientWidth || 900
    const H = svg.clientHeight || 600
    const R = 18 // node radius

    const fileIds = [...new Set(rawNodes.map(n => n.file_id))]
    const colorMap = new Map(fileIds.map((fid, i) => [fid, FILE_COLORS[i % FILE_COLORS.length]]))

    const nodes: NodeDatum[] = rawNodes.map(n => ({
      ...n,
      isExternal: m === 'file' && selectedFile ? n.file_id !== selectedFile.id : false,
      x: W / 2 + (Math.random() - 0.5) * 200,
      y: H / 2 + (Math.random() - 0.5) * 200,
    }))

    const nodeById = new Map(nodes.map(n => [n.id, n]))

    const edges: EdgeDatum[] = rawEdges
      .filter(e => nodeById.has(e.source as string) && nodeById.has(e.target as string))
      .map(e => ({ ...e, source: nodeById.get(e.source as string)!, target: nodeById.get(e.target as string)! }))

    const root = d3.select(svg)
    const g = root.append('g')

    root.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.05, 4])
        .on('zoom', e => g.attr('transform', e.transform))
    )

    root.append('defs').append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', R + 10)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#388bfd')

    const link = g.append('g').selectAll<SVGLineElement, EdgeDatum>('line')
      .data(edges).join('line')
      .attr('stroke', '#388bfd')
      .attr('stroke-width', 1.2)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrow)')

    const node = g.append('g').selectAll<SVGGElement, NodeDatum>('g')
      .data(nodes).join('g')
      .attr('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, NodeDatum>()
          .on('start', (event, d) => {
            if (!event.active) simRef.current?.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end', (event, d) => {
            if (!event.active) simRef.current?.alphaTarget(0)
            d.fx = null; d.fy = null
          })
      )
      .on('click', (event, d) => {
        event.stopPropagation()
        const deps = edges
          .filter(e => (e.source as NodeDatum).id === d.id || (e.target as NodeDatum).id === d.id)
          .map(e => {
            const src = e.source as NodeDatum
            const tgt = e.target as NodeDatum
            const other = src.id === d.id ? tgt : src
            return { id: other.id, name: other.name, file: other.file, direction: src.id === d.id ? 'calls' as const : 'called-by' as const }
          })
        setSelected({ node: d, deps })
        onNodeSelect(d.id, d.name)
        setTraceNodeId(d.id)
        setTraceNodeName(d.name)
        node.select('circle').attr('stroke', (n: NodeDatum) => n.id === d.id ? '#fff' : 'none').attr('stroke-width', 2)
        link
          .attr('stroke', (e: EdgeDatum) => {
            const s = (e.source as NodeDatum).id, t = (e.target as NodeDatum).id
            return s === d.id || t === d.id ? '#fff' : '#388bfd'
          })
          .attr('stroke-opacity', (e: EdgeDatum) => {
            const s = (e.source as NodeDatum).id, t = (e.target as NodeDatum).id
            return s === d.id || t === d.id ? 1 : 0.2
          })
      })

    root.on('click', () => {
      setSelected(null)
      node.select('circle').attr('stroke', 'none')
      link.attr('stroke', '#388bfd').attr('stroke-opacity', 0.6)
    })

    node.append('circle')
      .attr('r', R)
      .attr('fill', (d: NodeDatum) => colorMap.get(d.file_id) ?? '#58a6ff')
      .attr('fill-opacity', (d: NodeDatum) => d.isExternal ? 0.35 : 0.85)
      .attr('stroke', 'none')

    node.append('text')
      .text((d: NodeDatum) => d.name.length > 12 ? d.name.slice(0, 11) + '…' : d.name)
      .attr('text-anchor', 'middle')
      .attr('dy', R + 13)
      .attr('font-size', 10)
      .attr('fill', '#c9d1d9')
      .attr('pointer-events', 'none')

    const sim = d3.forceSimulation<NodeDatum>(nodes)
      .force('link', d3.forceLink<NodeDatum, EdgeDatum>(edges).id(d => d.id).distance(120).strength(0.5))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(R + 8))
      .on('tick', () => {
        link
          .attr('x1', (d: EdgeDatum) => (d.source as NodeDatum).x!)
          .attr('y1', (d: EdgeDatum) => (d.source as NodeDatum).y!)
          .attr('x2', (d: EdgeDatum) => (d.target as NodeDatum).x!)
          .attr('y2', (d: EdgeDatum) => (d.target as NodeDatum).y!)
        node.attr('transform', (d: NodeDatum) => `translate(${d.x},${d.y})`)
      })

    simRef.current = sim
  }, [repoId, selectedFile, onNodeSelect])

  useEffect(() => { draw(mode) }, [mode, selectedFile, draw])

  useEffect(() => {
    if (selectedFile) setMode('file')
  }, [selectedFile])

  useEffect(() => {
    const obs = new ResizeObserver(() => draw(mode))
    if (svgRef.current) obs.observe(svgRef.current)
    return () => obs.disconnect()
  }, [draw, mode])

  return (
    <div className="graph-panel">
      <div className="graph-toolbar">
        {(['full', 'file'] as GraphMode[]).map(m => (
          <button key={m} className={`btn-mode ${mode === m ? 'active' : ''}`} onClick={() => setMode(m)}>
            {m === 'full' ? 'Full Graph' : 'File View'}
          </button>
        ))}
        <button
          className={`btn-mode ${mode === 'flow' ? 'active' : ''}`}
          onClick={() => setMode('flow')}
        >
          Flow {traceNodeName ? `· ${traceNodeName}` : ''}
        </button>
        {mode !== 'flow' && <span className="graph-count">{nodeCount} nodes</span>}
      </div>

      {mode === 'flow' ? (
        <TracePanel repoId={repoId} nodeId={traceNodeId} nodeName={traceNodeName} />
      ) : (
        <>
          <svg ref={svgRef} width="100%" height="100%" />
          {selected && (
            <div className="node-inspector">
              <div className="inspector-header">
                <span className="inspector-name">{selected.node.name}()</span>
                <button className="inspector-close" onClick={() => setSelected(null)}>✕</button>
              </div>
              <div className="inspector-row"><span>File</span><code>{selected.node.file}</code></div>
              <div className="inspector-row"><span>Line</span><code>{selected.node.start_line}</code></div>
              {selected.node.summary && (
                <div className="inspector-row"><span>Summary</span><span>{selected.node.summary}</span></div>
              )}
              {selected.deps.length > 0 && (
                <div className="inspector-deps">
                  <div className="inspector-deps-title">Dependencies</div>
                  {selected.deps.map(d => (
                    <div key={d.id} className="inspector-dep">
                      <span className={`dep-badge ${d.direction}`}>{d.direction === 'calls' ? '→' : '←'}</span>
                      <span className="dep-name">{d.name}</span>
                      <span className="dep-file">{d.file.split('/').pop()}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
