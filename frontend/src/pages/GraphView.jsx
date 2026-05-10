import { useCallback, useEffect, useState } from 'react'
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow'
import 'reactflow/dist/style.css'
import { api } from '../api.js'

const TYPE_COLOR = {
  Asset: '#22d3ee', Concept: '#a855f7', Skill: '#10b981', Playbook: '#facc15',
  Mission: '#ec4899', Plan: '#f97316', Goal: '#fb7185', KPI: '#84cc16',
  Vision: '#06b6d4', Strategy: '#6366f1', Todo: '#94a3b8',
}

export default function GraphView() {
  const [center, setCenter] = useState('')
  const [hops, setHops] = useState(1)
  const [data, setData] = useState({ nodes: [], edges: [] })
  const [poisonOnly, setPoisonOnly] = useState(false)
  const [err, setErr] = useState(null)

  const load = useCallback(async () => {
    try {
      if (!center) return
      const sub = await api.kg.subgraph(center, hops)
      const nodes = sub.nodes.map((n, i) => {
        const angle = (i / Math.max(1, sub.nodes.length)) * 2 * Math.PI
        const r = n.id === center ? 0 : 250
        return {
          id: n.id,
          position: { x: 400 + r * Math.cos(angle), y: 300 + r * Math.sin(angle) },
          data: { label: <div className="text-[11px]"><div className="font-bold">{n.name}</div><div className="opacity-60">{n.type}</div></div> },
          style: {
            background: TYPE_COLOR[n.type] || '#475569',
            color: '#0b1020', borderRadius: 8, padding: 6, border: n.id === center ? '3px solid #fff' : 'none',
          },
        }
      })
      const edges = sub.edges
        .filter((e) => !poisonOnly)
        .map((e, i) => ({
          id: 'e' + i, source: e.src, target: e.dst, label: e.type,
          style: { stroke: '#94a3b8' }, labelStyle: { fontSize: 10, fill: '#94a3b8' },
        }))
      setData({ nodes, edges })
    } catch (e) { setErr(e.message) }
  }, [center, hops, poisonOnly])

  useEffect(() => { if (center) load() }, [center, hops, load])

  async function pickFirstAsset() {
    const ns = await api.kg.nodes({ type: 'Asset', limit: 1 })
    if (ns[0]) setCenter(ns[0].id)
  }
  useEffect(() => { if (!center) pickFirstAsset() }, [])

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div>
        <h1 className="text-2xl font-bold">Graph View</h1>
        <p className="text-ink-100/60 text-sm">중심 노드를 정하고 N-hop 이웃을 시각화. 변조 후 새 엣지가 명시적으로 보임.</p>
      </div>
      <div className="card flex flex-wrap gap-2 items-center">
        <input className="input flex-1 min-w-[200px]" placeholder="center node id" value={center} onChange={(e) => setCenter(e.target.value)} />
        <select className="input max-w-[100px]" value={hops} onChange={(e) => setHops(+e.target.value)}>
          {[1,2,3].map((h) => <option key={h} value={h}>{h}-hop</option>)}
        </select>
        <button className="btn-primary" onClick={load}>load</button>
        <label className="text-xs flex items-center gap-1 ml-2"><input type="checkbox" checked={poisonOnly} onChange={(e) => setPoisonOnly(e.target.checked)} /> hide edges</label>
      </div>
      {err && <div className="text-attack-500 text-sm">{err}</div>}
      <div className="card flex-1" style={{ minHeight: 500 }}>
        <ReactFlow nodes={data.nodes} edges={data.edges} fitView>
          <Background color="#334" gap={16} />
          <MiniMap nodeColor={(n) => n.style?.background || '#475569'} />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  )
}
