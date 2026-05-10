import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Experiments() {
  const [exps, setExps] = useState([])
  const [editing, setEditing] = useState(null)
  const [picked, setPicked] = useState(null)

  const reload = () => api.experiments.list().then(setExps)
  useEffect(reload, [])

  async function open(id) { setPicked(await api.experiments.get(id)) }
  async function save() {
    await api.experiments.create(editing)
    setEditing(null); reload()
  }
  async function status(id, s) { await api.experiments.setStatus(id, s); reload(); if (picked?.experiment.id === id) open(id) }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Experiments</h1>
          <p className="text-ink-100/60 text-sm">실험 단위로 manipulation+pentest+defense 결과 묶기.</p>
        </div>
        <button className="btn-primary" onClick={() => setEditing({ kind: 'manipulation', title: '', description: '', params: {} })}>+ 새 실험</button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card scroll-area" style={{ maxHeight: 600 }}>
          <table className="tbl"><thead><tr><th>id</th><th>kind</th><th>title</th><th>status</th><th /></tr></thead>
            <tbody>
              {exps.map((e) => (
                <tr key={e.id} className={'cursor-pointer ' + (picked?.experiment.id === e.id ? 'bg-kg-600/10' : '')}>
                  <td onClick={() => open(e.id)}>#{e.id}</td>
                  <td onClick={() => open(e.id)}><span className="tag">{e.kind}</span></td>
                  <td onClick={() => open(e.id)}>{e.title}</td>
                  <td>
                    <select className="input text-xs" value={e.status} onChange={(ev) => status(e.id, ev.target.value)}>
                      <option>planned</option><option>running</option><option>done</option><option>failed</option><option>cancelled</option>
                    </select>
                  </td>
                  <td className="text-xs text-ink-100/60">{e.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          {!picked && <div className="text-ink-100/60 text-sm">실험 선택 시 runs/notes 표시</div>}
          {picked && (
            <div className="space-y-3">
              <div>
                <div className="text-xs text-ink-100/60">{picked.experiment.kind}</div>
                <div className="text-lg font-semibold">{picked.experiment.title}</div>
                <div className="text-xs text-ink-100/70 whitespace-pre-wrap">{picked.experiment.description}</div>
              </div>
              <div>
                <div className="text-xs text-ink-100/60 mb-1">runs ({picked.runs.length})</div>
                <div className="space-y-1">
                  {picked.runs.map((r) => (
                    <div key={r.id} className="bg-ink-950 p-2 rounded text-[11px]">
                      <span className="tag-attack">{r.phase}</span> #{r.id} · {r.created_at}
                      <pre className="mt-1 overflow-auto" style={{ maxHeight: 100 }}>{r.result}</pre>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs text-ink-100/60 mb-1">notes ({picked.notes.length})</div>
                {picked.notes.map((n) => (
                  <div key={n.id} className="bg-ink-950 p-2 rounded text-[11px] mb-1">
                    {n.tag && <span className="tag mr-2">{n.tag}</span>}
                    <span className="whitespace-pre-wrap">{n.body}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setEditing(null)}>
          <div className="card w-[600px]" onClick={(e) => e.stopPropagation()}>
            <div className="text-lg font-semibold mb-2">새 실험</div>
            <select className="input mb-2" value={editing.kind} onChange={(e) => setEditing({ ...editing, kind: e.target.value })}>
              <option>manipulation</option><option>pentest</option><option>defense</option><option>combined</option>
            </select>
            <input className="input mb-2" placeholder="title" value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} />
            <textarea className="input mb-2" rows={4} placeholder="description / hypothesis" value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
            <div className="flex gap-2 justify-end">
              <button className="btn-ghost" onClick={() => setEditing(null)}>cancel</button>
              <button className="btn-primary" onClick={save}>create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
