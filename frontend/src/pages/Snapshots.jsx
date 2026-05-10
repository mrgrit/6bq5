import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Snapshots() {
  const [snaps, setSnaps] = useState([])
  const [label, setLabel] = useState('')
  const [diff, setDiff] = useState(null)

  const reload = () => api.kg.snapshots().then(setSnaps)
  useEffect(reload, [])

  async function take() {
    if (!label) return
    await api.kg.snapshot(label, ''); setLabel(''); reload()
  }
  async function showDiff(id) { setDiff(await api.kg.diff(id)) }
  async function restore(id) { if (confirm('Restore snapshot ' + id + '? This wipes live KG.')) { await api.kg.restore(id); reload() } }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">KG Snapshots</h1>
        <p className="text-ink-100/60 text-sm">변조 전 baseline 저장 · diff · rollback. 모든 실험은 snapshot → poison → diff 워크플로우 권장.</p>
      </div>

      <div className="card flex gap-2">
        <input className="input flex-1" placeholder="snapshot label" value={label} onChange={(e) => setLabel(e.target.value)} />
        <button className="btn-defense" onClick={take}>📸 take</button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card scroll-area" style={{ maxHeight: 600 }}>
          <table className="tbl"><thead><tr><th>id</th><th>label</th><th>n</th><th>e</th><th>at</th><th /></tr></thead>
            <tbody>
              {snaps.map((s) => (
                <tr key={s.id}>
                  <td>#{s.id}</td>
                  <td>{s.label}</td>
                  <td>{s.node_count}</td>
                  <td>{s.edge_count}</td>
                  <td className="text-[11px] text-ink-100/60">{s.created_at}</td>
                  <td className="space-x-1 text-xs">
                    <button onClick={() => showDiff(s.id)}>diff</button>
                    <button className="text-attack-500" onClick={() => restore(s.id)}>restore</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          {!diff && <div className="text-ink-100/60 text-sm">diff 결과가 여기에…</div>}
          {diff && (
            <div className="space-y-2">
              <div className="font-semibold">diff vs live (snapshot #{diff.snapshot_id})</div>
              <pre className="bg-ink-950 p-2 rounded text-[11px]">{JSON.stringify(diff.summary, null, 2)}</pre>
              <details><summary className="text-xs cursor-pointer">added nodes ({diff.added_nodes.length})</summary>
                <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 200 }}>{JSON.stringify(diff.added_nodes.slice(0, 30), null, 2)}</pre>
              </details>
              <details><summary className="text-xs cursor-pointer">removed nodes ({diff.removed_nodes.length})</summary>
                <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 200 }}>{JSON.stringify(diff.removed_nodes.slice(0, 30), null, 2)}</pre>
              </details>
              <details><summary className="text-xs cursor-pointer">changed nodes ({diff.changed_nodes.length})</summary>
                <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 200 }}>{JSON.stringify(diff.changed_nodes.slice(0, 20), null, 2)}</pre>
              </details>
              <details><summary className="text-xs cursor-pointer">added/removed edges ({diff.added_edges.length}/{diff.removed_edges.length})</summary>
                <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 200 }}>{JSON.stringify({added: diff.added_edges.slice(0, 20), removed: diff.removed_edges.slice(0, 20)}, null, 2)}</pre>
              </details>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
