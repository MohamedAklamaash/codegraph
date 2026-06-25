import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import * as d3 from 'd3'
import type { RepoFile, FunctionNode, FunctionEdge } from '../types'
import { api } from '../api'
import { TracePanel } from './TracePanel'

type GraphMode = 'full' | 'file' | 'dir' | 'flow'

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
  selectedDir: string | null
  onNodeSelect: (id: string, name: string) => void
  /** Node to focus/center (set by chat citations). */
  focusNodeId?: string | null
  /** Bumped on every focus request so repeat clicks on the same node re-trigger. */
  focusNonce?: number
}

const FILE_COLORS = [
  '#6366f1', '#22d3ee', '#34d399', '#fbbf24',
  '#f472b6', '#a78bfa', '#fb923c', '#38bdf8',
]

export function GraphPanel({ repoId, selectedFile, selectedDir, onNodeSelect, focusNodeId, focusNonce }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simRef = useRef<d3.Simulation<NodeDatum, EdgeDatum> | null>(null)
  // focusOn for the current drawing; lets the focus effect center a node
  // without re-running draw. pendingFocus holds an id to apply after a redraw.
  const focusFnRef = useRef<((id: string) => boolean) | null>(null)
  const pendingFocusRef = useRef<string | null>(null)
  const [mode, setMode] = useState<GraphMode>('full')
  const [selected, setSelected] = useState<SelectedNode | null>(null)
  const [nodeCount, setNodeCount] = useState(0)
  const [hiddenCount, setHiddenCount] = useState(0)
  const [showAll, setShowAll] = useState(false)
  const [traceNodeId, setTraceNodeId] = useState<string | null>(null)
  const [traceNodeName, setTraceNodeName] = useState<string | null>(null)

  const draw = useCallback(async (m: GraphMode) => {
    const svg = svgRef.current
    if (!svg || m === 'flow') return

    const params: { file_id?: number; dir?: string; include_boilerplate?: boolean } = {}
    if (m === 'file' && selectedFile) params.file_id = selectedFile.id
    if (m === 'dir' && selectedDir) params.dir = selectedDir
    if (showAll) params.include_boilerplate = true

    // Boilerplate (__init__, dunders) is filtered server-side unless "Show all".
    let rawNodes: FunctionNode[], rawEdges: FunctionEdge[], hidden: number
    try {
      const data = await api.getGraph(repoId, params)
      rawNodes = data.nodes
      rawEdges = data.edges
      hidden = data.hidden ?? 0
    } catch { return }

    setNodeCount(rawNodes.length)
    setHiddenCount(hidden)

    simRef.current?.stop()
    d3.select(svg).selectAll('*').remove()

    const W = svg.clientWidth || 900
    const H = svg.clientHeight || 600
    const R = 18 // node radius

    // Read brand colors from CSS vars so the graph re-themes with light/dark.
    const cs = getComputedStyle(svg)
    const accentColor = cs.getPropertyValue('--accent').trim() || '#d97757'
    const textColor = cs.getPropertyValue('--text').trim() || '#f0e6dc'

    const fileIds = [...new Set(rawNodes.map(n => n.file_id))]
    const colorMap = new Map(fileIds.map((fid, i) => [fid, FILE_COLORS[i % FILE_COLORS.length]]))

    const nodes: NodeDatum[] = rawNodes.map(n => ({
      ...n,
      isExternal: m === 'file' && selectedFile
          ? n.file_id !== selectedFile.id
          : m === 'dir' && selectedDir
            ? !n.file.startsWith(selectedDir + '/')
            : false,
      x: W / 2 + (Math.random() - 0.5) * 200,
      y: H / 2 + (Math.random() - 0.5) * 200,
    }))

    const nodeById = new Map(nodes.map(n => [n.id, n]))

    const edges: EdgeDatum[] = rawEdges
      .filter(e => nodeById.has(e.source as string) && nodeById.has(e.target as string))
      .map(e => ({ ...e, source: nodeById.get(e.source as string)!, target: nodeById.get(e.target as string)! }))

    const root = d3.select(svg)
    const g = root.append('g')

    const zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 4])
      .on('zoom', e => g.attr('transform', e.transform))
    root.call(zoomBehavior)

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
      .attr('fill', accentColor)

    const link = g.append('g').selectAll<SVGLineElement, EdgeDatum>('line')
      .data(edges).join('line')
      .attr('stroke', accentColor)
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
        node.select('circle').attr('stroke', (n: NodeDatum) => n.id === d.id ? textColor : 'none').attr('stroke-width', 2)
        link
          .attr('stroke', (e: EdgeDatum) => {
            const s = (e.source as NodeDatum).id, t = (e.target as NodeDatum).id
            return s === d.id || t === d.id ? textColor : accentColor
          })
          .attr('stroke-opacity', (e: EdgeDatum) => {
            const s = (e.source as NodeDatum).id, t = (e.target as NodeDatum).id
            return s === d.id || t === d.id ? 1 : 0.2
          })
      })

    root.on('click', () => {
      setSelected(null)
      node.select('circle').attr('stroke', 'none')
      link.attr('stroke', accentColor).attr('stroke-opacity', 0.6)
    })

    // Imperative focus used by chat citations: highlight a node + its edges and
    // pan/zoom it to the center. Returns false when the id isn't in this view.
    const focusOn = (id: string): boolean => {
      const d = nodes.find(n => n.id === id)
      if (!d) return false
      const deps = edges
        .filter(e => (e.source as NodeDatum).id === d.id || (e.target as NodeDatum).id === d.id)
        .map(e => {
          const src = e.source as NodeDatum
          const tgt = e.target as NodeDatum
          const other = src.id === d.id ? tgt : src
          return { id: other.id, name: other.name, file: other.file, direction: src.id === d.id ? 'calls' as const : 'called-by' as const }
        })
      setSelected({ node: d, deps })
      setTraceNodeId(d.id)
      setTraceNodeName(d.name)
      node.select('circle').attr('stroke', (n: NodeDatum) => n.id === d.id ? textColor : 'none').attr('stroke-width', 2)
      link
        .attr('stroke', (e: EdgeDatum) => {
          const s = (e.source as NodeDatum).id, t = (e.target as NodeDatum).id
          return s === d.id || t === d.id ? '#f0e6dc' : '#d97757'
        })
        .attr('stroke-opacity', (e: EdgeDatum) => {
          const s = (e.source as NodeDatum).id, t = (e.target as NodeDatum).id
          return s === d.id || t === d.id ? 1 : 0.2
        })
      const scale = 1.4
      const tx = W / 2 - (d.x ?? W / 2) * scale
      const ty = H / 2 - (d.y ?? H / 2) * scale
      root.transition().duration(500).call(
        zoomBehavior.transform,
        d3.zoomIdentity.translate(tx, ty).scale(scale),
      )
      return true
    }
    focusFnRef.current = focusOn

    node.append('circle')
      .attr('r', R)
      .attr('fill', (d: NodeDatum) => colorMap.get(d.file_id) ?? accentColor)
      .attr('fill-opacity', (d: NodeDatum) => d.isExternal ? 0.35 : 0.85)
      .attr('stroke', 'none')

    node.append('text')
      .text((d: NodeDatum) => d.name.length > 12 ? d.name.slice(0, 11) + '…' : d.name)
      .attr('text-anchor', 'middle')
      .attr('dy', R + 13)
      .attr('font-size', 10)
      .attr('fill', textColor)
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
      .on('end', () => {
        // Apply a focus requested before/while the layout was settling, now
        // that node positions are final.
        if (pendingFocusRef.current && focusOn(pendingFocusRef.current)) {
          pendingFocusRef.current = null
        }
      })

    simRef.current = sim
  }, [repoId, selectedFile, selectedDir, onNodeSelect, showAll])

  // A citation was clicked: ensure the full graph is shown (so the node exists)
  // and center it. Try immediately for the already-drawn case; otherwise let the
  // redraw's 'end' handler apply the pending focus.
  useEffect(() => {
    if (!focusNodeId) return
    setMode('full')
    pendingFocusRef.current = focusNodeId
    if (focusFnRef.current?.(focusNodeId)) {
      pendingFocusRef.current = null
    }
  }, [focusNodeId, focusNonce])

  useEffect(() => { draw(mode) }, [mode, selectedFile, selectedDir, draw])

  useEffect(() => {
    if (selectedFile) setMode('file')
  }, [selectedFile])

  useEffect(() => {
    if (selectedDir) setMode('dir')
  }, [selectedDir])

  useEffect(() => {
    const obs = new ResizeObserver(() => draw(mode))
    if (svgRef.current) obs.observe(svgRef.current)
    return () => obs.disconnect()
  }, [draw, mode])

  // Re-read CSS-var colors when the theme flips.
  useEffect(() => {
    const onThemeChange = () => draw(mode)
    window.addEventListener('theme:change', onThemeChange)
    return () => window.removeEventListener('theme:change', onThemeChange)
  }, [draw, mode])

  return (
    <div className="graph-panel">
      <div className="graph-toolbar">
        {(['full', 'file'] as GraphMode[]).map(m => (
          <button key={m} className={`btn-mode ${mode === m ? 'active' : ''}`} onClick={() => setMode(m)}>
            {m === 'full' ? 'Full Graph' : 'File View'}
          </button>
        ))}
        {selectedDir && (
          <button className={`btn-mode ${mode === 'dir' ? 'active' : ''}`} onClick={() => setMode('dir')}>
            Dir View
          </button>
        )}
        <button
          className={`btn-mode ${mode === 'flow' ? 'active' : ''}`}
          onClick={() => setMode('flow')}
        >
          Flow {traceNodeName ? `· ${traceNodeName}` : ''}
        </button>
        {mode !== 'flow' && (
          <button
            className={`btn-mode ${showAll ? 'active' : ''}`}
            onClick={() => setShowAll(s => !s)}
            title={showAll ? 'Showing every function' : `Hiding ${hiddenCount} boilerplate function${hiddenCount === 1 ? '' : 's'} (__init__, dunders)`}
          >
            {showAll ? 'All functions' : 'User-defined'}
          </button>
        )}
        {mode !== 'flow' && (
          <span className="graph-count">
            {nodeCount} nodes{!showAll && hiddenCount > 0 ? ` · ${hiddenCount} hidden` : ''}
          </span>
        )}
      </div>

      {mode === 'flow' ? (
        <TracePanel repoId={repoId} nodeId={traceNodeId} nodeName={traceNodeName} />
      ) : (
        <>
          <svg ref={svgRef} width="100%" height="100%" />
          {nodeCount === 0 && (
            <div className="graph-empty">
              <div className="graph-empty-glyph">⌘</div>
              <p>No functions to show here</p>
              <span>Pick a file or switch to Full Graph</span>
            </div>
          )}
          <AnimatePresence>
            {selected && (
              <motion.div
                className="node-inspector"
                initial={{ opacity: 0, y: 12, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 12, scale: 0.98 }}
                transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              >
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
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  )
}
