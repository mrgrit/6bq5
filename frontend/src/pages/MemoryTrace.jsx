import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function MemoryTrace() {
  const [list, setList] = useState([])
  const [agent, setAgent] = useState('bastion')
  const [op, setOp] = useState('write')
  const [nodeId, setNodeId] = useState('')
  const [content, setContent] = useState('')
  const [eid, setEid] = useState('')
  const [exps, setExps] = useState([])

  const reload = () => api.memory.list().then(setList)
  useEffect(() => { reload(); api.experiments.list().then(setExps) }, [])

  async function record() {
    await api.memory.record({ agent, op, node_id: nodeId, content, experiment_id: eid ? +eid : null })
    setContent(''); reload()
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Memory Trace</h1>
        <p className="text-ink-100/60 text-sm">에이전트의 long-term memory write/read/rollback 기록 (MINJA / IsolateGPT NDSS'25 inspired).</p>
      </div>

      <div className="card space-y-2">
        <div className="grid grid-cols-4 gap-2">
          <input className="input" placeholder="agent" value={agent} onChange={(e) => setAgent(e.target.value)} />
          <select className="input" value={op} onChange={(e) => setOp(e.target.value)}>
            <option>write</option><option>read</option><option>rollback</option>
          </select>
          <input className="input" placeholder="node_id (optional)" value={nodeId} onChange={(e) => setNodeId(e.target.value)} />
          <select className="input" value={eid} onChange={(e) => setEid(e.target.value)}>
            <option value="">(no experiment)</option>
            {exps.map((e) => <option key={e.id} value={e.id}>#{e.id} {e.title}</option>)}
          </select>
        </div>
        <textarea className="input" rows={3} placeholder="content / payload" value={content} onChange={(e) => setContent(e.target.value)} />
        <div className="flex justify-end"><button className="btn-attack" onClick={record}>+ record</button></div>
      </div>

      <div className="card scroll-area" style={{ maxHeight: 600 }}>
        <table className="tbl"><thead><tr><th>ts</th><th>agent</th><th>op</th><th>node</th><th>content</th></tr></thead>
          <tbody>
            {list.map((m) => (
              <tr key={m.id}>
                <td className="text-[11px] text-ink-100/60">{m.ts}</td>
                <td>{m.agent}</td>
                <td><span className={'tag ' + (m.op === 'write' ? 'bg-attack-600/30 text-attack-500' : m.op === 'rollback' ? 'bg-defense-600/30 text-defense-500' : '')}>{m.op}</span></td>
                <td className="text-[11px] font-mono">{m.node_id}</td>
                <td className="text-[11px] text-ink-100/80 max-w-[400px] truncate">{m.content}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
