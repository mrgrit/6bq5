import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Notes() {
  const [list, setList] = useState([])
  const [body, setBody] = useState('')
  const [tag, setTag] = useState('idea')
  const [eid, setEid] = useState('')
  const [exps, setExps] = useState([])
  const [filter, setFilter] = useState('')

  const reload = () => api.notes.list().then(setList)
  useEffect(() => { reload(); api.experiments.list().then(setExps) }, [])

  async function add() {
    if (!body.trim()) return
    await api.notes.create(body, tag, eid ? +eid : null)
    setBody(''); reload()
  }

  const filtered = filter ? list.filter((n) => (n.body + ' ' + (n.tag || '')).toLowerCase().includes(filter.toLowerCase())) : list

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Journal · Notes</h1>
        <p className="text-ink-100/60 text-sm">관찰 · 가설 · 결과 · 다음 액션. 실험 ID에 묶을 수 있음.</p>
      </div>

      <div className="card space-y-2">
        <textarea className="input" rows={4} placeholder="markdown 가능…" value={body} onChange={(e) => setBody(e.target.value)} />
        <div className="flex gap-2">
          <select className="input max-w-[160px]" value={tag} onChange={(e) => setTag(e.target.value)}>
            <option>idea</option><option>observation</option><option>hypothesis</option><option>result</option><option>todo</option><option>incident</option>
          </select>
          <select className="input max-w-[200px]" value={eid} onChange={(e) => setEid(e.target.value)}>
            <option value="">(no experiment)</option>
            {exps.map((e) => <option key={e.id} value={e.id}>#{e.id} {e.title}</option>)}
          </select>
          <button className="btn-primary ml-auto" onClick={add}>+ add note</button>
        </div>
      </div>

      <div className="card flex gap-2">
        <input className="input" placeholder="filter…" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>

      <div className="space-y-2">
        {filtered.map((n) => (
          <div key={n.id} className="card">
            <div className="flex justify-between text-xs text-ink-100/60 mb-1">
              <div>{n.tag && <span className="tag mr-2">{n.tag}</span>}{n.experiment_id && <span className="tag-attack">exp #{n.experiment_id}</span>}</div>
              <div>{n.created_at}</div>
            </div>
            <div className="whitespace-pre-wrap text-sm">{n.body}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
