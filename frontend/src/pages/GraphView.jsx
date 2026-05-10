import { useCallback, useEffect, useState } from 'react'
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow'
import 'reactflow/dist/style.css'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const TYPE_COLOR = {
  Asset: '#22d3ee', Concept: '#a855f7', Skill: '#10b981', Playbook: '#facc15',
  Mission: '#ec4899', Plan: '#f97316', Goal: '#fb7185', KPI: '#84cc16',
  Vision: '#06b6d4', Strategy: '#6366f1', Todo: '#94a3b8', Experience: '#f43f5e',
}

export default function GraphView() {
  const [center, setCenter] = useState('')
  const [hops, setHops] = useState(1)
  const [data, setData] = useState({ nodes: [], edges: [], anchor: null })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [topNodes, setTopNodes] = useState([])
  const [searchQ, setSearchQ] = useState('')
  const [searchHits, setSearchHits] = useState([])
  const [warn, setWarn] = useState(null)

  // 진입 시: importance 상위 30개 미리 받아 추천 패널
  useEffect(() => {
    api.kg.importance(30).then((rs) => {
      setTopNodes(rs)
      if (!center && rs[0]) setCenter(rs[0].id)
    }).catch((e) => setErr(e.message))
  }, [])

  // search
  useEffect(() => {
    if (!searchQ.trim()) { setSearchHits([]); return }
    const id = setTimeout(async () => {
      try {
        const ns = await api.kg.nodes({ q: searchQ, limit: 20 })
        setSearchHits(ns)
      } catch {}
    }, 250)
    return () => clearTimeout(id)
  }, [searchQ])

  const load = useCallback(async () => {
    if (!center) return
    setLoading(true); setErr(null); setWarn(null)
    try {
      const sub = await api.kg.subgraph(center, hops)
      if (!sub.nodes.length) {
        setWarn(`'${center}' 노드를 찾을 수 없음`)
        setData({ nodes: [], edges: [], anchor: center })
        return
      }
      if (sub.nodes.length === 1 && !sub.edges.length) {
        setWarn(`'${center}' 는 고립 노드 (이웃 없음). 다른 노드를 선택하거나 hops 를 늘리세요.`)
      }
      // radial layout
      const others = sub.nodes.filter((n) => n.id !== center)
      const n = others.length
      const cx = 500, cy = 350, r = 260
      const nodes = [
        {
          id: center,
          position: { x: cx, y: cy },
          data: { label: <div className="text-[11px]"><div className="font-bold">{(sub.nodes.find((x) => x.id === center) || {}).name || center}</div><div className="opacity-70 text-[10px]">{(sub.nodes.find((x) => x.id === center) || {}).type}</div></div> },
          style: {
            background: TYPE_COLOR[(sub.nodes.find((x) => x.id === center) || {}).type] || '#475569',
            color: '#0b1020', borderRadius: 10, padding: 8, border: '3px solid #fff', minWidth: 90,
          },
        },
        ...others.map((nn, i) => {
          const a = (i / Math.max(1, n)) * 2 * Math.PI
          return {
            id: nn.id,
            position: { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) },
            data: { label: <div className="text-[10px]"><div className="font-semibold truncate" style={{maxWidth:120}}>{nn.name}</div><div className="opacity-60">{nn.type}</div></div> },
            style: {
              background: TYPE_COLOR[nn.type] || '#475569',
              color: '#0b1020', borderRadius: 8, padding: 5, fontSize: 10,
            },
          }
        }),
      ]
      const edges = sub.edges.map((e, i) => ({
        id: 'e' + i, source: e.src, target: e.dst,
        label: e.type, animated: e.meta?.poison === true,
        style: { stroke: e.meta?.poison ? '#ef4444' : '#94a3b8' },
        labelStyle: { fontSize: 9, fill: '#cbd5e1' },
      }))
      setData({ nodes, edges, anchor: center })
    } catch (e) { setErr(e.message) }
    finally { setLoading(false) }
  }, [center, hops])

  useEffect(() => { if (center) load() }, [center, hops, load])

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div>
        <h1 className="text-2xl font-bold">Graph View</h1>
        <p className="text-ink-100/60 text-sm">중심 노드 N-hop 이웃 시각화. <span className="text-attack-500">빨간 엣지</span> = poison 마크.</p>
      </div>

      <div className="card flex flex-wrap gap-2 items-center">
        <input
          className="input flex-1 min-w-[260px] font-mono text-xs"
          placeholder="center node id (자동완성 — 아래 검색 박스)"
          value={center}
          onChange={(e) => setCenter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && load()}
        />
        <select className="input max-w-[100px]" value={hops} onChange={(e) => setHops(+e.target.value)}>
          {[1,2,3,4].map((h) => <option key={h} value={h}>{h}-hop</option>)}
        </select>
        <button className="btn-primary" disabled={loading} onClick={load}>{loading ? '…' : 'load'}</button>
      </div>

      <div className="grid md:grid-cols-4 gap-3" style={{ minHeight: 500 }}>
        <div className="md:col-span-1 card scroll-area" style={{ maxHeight: 600 }}>
          <div className="text-xs text-ink-100/60 mb-1">노드 검색</div>
          <input className="input mb-2" placeholder="이름 또는 id…"
                 value={searchQ} onChange={(e) => setSearchQ(e.target.value)} />
          {searchHits.length > 0 && (
            <div className="space-y-1 mb-3">
              {searchHits.map((n) => (
                <div key={n.id}
                     onClick={() => { setCenter(n.id); setSearchQ('') }}
                     className="cursor-pointer text-[11px] p-1 rounded hover:bg-ink-100/10">
                  <div className="font-mono">{n.id}</div>
                  <div className="text-ink-100/60">{n.type} · {n.name?.slice(0, 50)}</div>
                </div>
              ))}
            </div>
          )}

          <div className="text-xs text-ink-100/60 mb-1 mt-3">중심 추천 (PageRank top 30)</div>
          <div className="space-y-1">
            {topNodes.map((n, i) => (
              <div key={n.id}
                   onClick={() => setCenter(n.id)}
                   className={'cursor-pointer text-[11px] p-1 rounded hover:bg-ink-100/10 ' + (n.id === center ? 'bg-kg-600/20' : '')}>
                <div className="flex justify-between">
                  <span className="font-mono truncate" style={{ maxWidth: 140 }}>{n.id}</span>
                  <span className="text-ink-100/40">{n.in_degree + n.out_degree}d</span>
                </div>
                <div className="text-ink-100/60">{n.type} · pr={n.pagerank.toFixed(4)}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="md:col-span-3 card flex flex-col" style={{ minHeight: 500 }}>
          {warn && <div className="text-amber-400 text-xs mb-2 px-2 py-1 bg-amber-500/10 rounded">⚠ {warn}</div>}
          {err && <div className="text-attack-500 text-xs mb-2">{err}</div>}
          <div className="text-[11px] text-ink-100/60 mb-1">
            center: <span className="font-mono text-ink-100/80">{center || '-'}</span> · {data.nodes.length} 노드 · {data.edges.length} 엣지
            {' · '}
            <Link className="text-kg-500 hover:underline" to={'/kg?id=' + encodeURIComponent(center)}>open in Explorer →</Link>
          </div>
          <div className="flex-1" style={{ minHeight: 480 }}>
            <ReactFlow nodes={data.nodes} edges={data.edges} fitView minZoom={0.2}>
              <Background color="#334" gap={16} />
              <MiniMap nodeColor={(n) => n.style?.background || '#475569'} pannable />
              <Controls />
            </ReactFlow>
          </div>
        </div>
      </div>
    </div>
  )
}
