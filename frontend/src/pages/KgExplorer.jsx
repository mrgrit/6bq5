import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api.js'

const NODE_TYPES = ['Asset','Concept','Goal','KPI','Mission','Plan','Playbook','Skill','Strategy','Todo','Vision']
const EDGE_TYPES = ['uses','handles','targets','supersedes','depends_on','often_chains','derived_from','encountered','recovered_by','applied_in','parent_of','abstracts','reuse','adapt','generalize','refute','precedes','follows','belongs_to','relates_to','connects_to','data_flows_to','hosts','manages','trusts','monitors','realizes','measures','contributes_to','blocks','owned_by','scheduled_for','derives_from']

export default function KgExplorer() {
  const [params, setParams] = useSearchParams()
  const [type, setType] = useState(params.get('type') || '')
  const [q, setQ] = useState(params.get('q') || '')
  const [nodes, setNodes] = useState([])
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState(null)
  const [neighbors, setNeighbors] = useState([])

  const reload = () => {
    api.kg.nodes({ type, q, limit: 200 }).then(setNodes).catch((e) => setError(e.message))
  }
  useEffect(reload, [type, q])

  useEffect(() => {
    const id = params.get('id')
    if (id) loadNode(id)
  }, [])

  async function loadNode(id) {
    try {
      const n = await api.kg.node(id)
      setSelected(n)
      const sub = await api.kg.subgraph(id, 1)
      setNeighbors(sub.edges)
    } catch (e) {
      setError(e.message)
    }
  }

  async function save() {
    try {
      await api.kg.upsertNode(editing)
      setEditing(null)
      reload()
      if (selected) loadNode(selected.id)
    } catch (e) { setError(e.message) }
  }

  async function del(id) {
    if (!confirm('Delete ' + id + ' ?')) return
    await api.kg.deleteNode(id)
    setSelected(null); setNeighbors([]); reload()
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">KG Explorer</h1>
        <p className="text-ink-100/60 text-sm">노드 검색 · 조회 · 편집 · 삭제. Live KG = poison 후 변경된 상태.</p>
      </div>

      <div className="card flex gap-2 items-center">
        <select className="input max-w-[180px]" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">(all types)</option>
          {NODE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input className="input flex-1" placeholder="search by id or name…" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn-primary" onClick={() => setEditing({ id: '', type: 'Asset', name: '', content: {}, meta: {} })}>+ New</button>
      </div>

      {error && <div className="card border-attack-500/40 text-attack-500 text-sm">{error}</div>}

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <div className="text-xs text-ink-100/60 mb-1">{nodes.length} matches</div>
          <div className="scroll-area" style={{ maxHeight: 600 }}>
            <table className="tbl">
              <thead><tr><th>type</th><th>id / name</th><th /></tr></thead>
              <tbody>
                {nodes.map((n) => (
                  <tr key={n.id} className={'cursor-pointer hover:bg-ink-100/5 ' + (selected?.id === n.id ? 'bg-kg-600/10' : '')}>
                    <td onClick={() => loadNode(n.id)}><span className="tag-kg">{n.type}</span></td>
                    <td onClick={() => loadNode(n.id)} className="font-mono text-xs">{n.id}<div className="text-ink-100/70">{n.name}</div></td>
                    <td onClick={() => del(n.id)} className="text-attack-500 text-xs cursor-pointer">del</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          {!selected && <div className="text-ink-100/60 text-sm">노드 선택 시 상세</div>}
          {selected && (
            <div className="space-y-2">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs text-ink-100/60">{selected.type}</div>
                  <div className="text-lg font-semibold">{selected.name}</div>
                  <div className="text-[11px] font-mono text-ink-100/60">{selected.id}</div>
                </div>
                <div className="flex gap-2">
                  <button className="btn-ghost" onClick={() => setEditing({ ...selected })}>edit</button>
                  <button className="btn-attack" onClick={() => del(selected.id)}>del</button>
                </div>
              </div>
              <div className="text-xs text-ink-100/60">content</div>
              <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 200 }}>
{JSON.stringify(selected.content, null, 2)}
              </pre>
              <div className="text-xs text-ink-100/60">meta</div>
              <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 120 }}>
{JSON.stringify(selected.meta, null, 2)}
              </pre>
              <div className="text-xs text-ink-100/60 mt-2">neighbors ({neighbors.length})</div>
              <div className="space-y-1">
                {neighbors.slice(0, 30).map((e, i) => (
                  <div key={i} className="text-xs font-mono">
                    <span className="tag">{e.type}</span> {e.src === selected.id ? '→' : '←'} {e.src === selected.id ? e.dst : e.src}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setEditing(null)}>
          <div className="card w-[600px] max-w-[90vw] space-y-3" onClick={(e) => e.stopPropagation()}>
            <div className="text-lg font-semibold">노드 편집</div>
            <div className="grid grid-cols-2 gap-2">
              <input className="input" placeholder="id" value={editing.id} onChange={(e) => setEditing({ ...editing, id: e.target.value })} />
              <select className="input" value={editing.type} onChange={(e) => setEditing({ ...editing, type: e.target.value })}>
                {NODE_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
            <input className="input" placeholder="name" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            <textarea className="input font-mono text-xs" rows={5} placeholder='content (JSON)' value={JSON.stringify(editing.content || {}, null, 2)} onChange={(e) => { try { setEditing({ ...editing, content: JSON.parse(e.target.value) }) } catch {} }} />
            <textarea className="input font-mono text-xs" rows={3} placeholder='meta (JSON)' value={JSON.stringify(editing.meta || {}, null, 2)} onChange={(e) => { try { setEditing({ ...editing, meta: JSON.parse(e.target.value) }) } catch {} }} />
            <div className="flex gap-2 justify-end">
              <button className="btn-ghost" onClick={() => setEditing(null)}>cancel</button>
              <button className="btn-primary" onClick={save}>save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
