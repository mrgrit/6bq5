import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function ValueMatrix() {
  const [rows, setRows] = useState([])
  const [k, setK] = useState(50)
  const [loading, setLoading] = useState(false)
  const [sort, setSort] = useState('pagerank')

  const load = async () => {
    setLoading(true)
    try { setRows(await api.kg.importance(k)) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [k])

  const sorted = [...rows].sort((a, b) => (b[sort] || 0) - (a[sort] || 0))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Node Value Matrix</h1>
        <p className="text-ink-100/60 text-sm">PageRank · betweenness · degree — 공격 ROI 가 큰 노드 식별 (Clean-Label Backdoor AAAI'25, ROAR USENIX'23 inspired).</p>
      </div>
      <div className="card flex gap-2 items-center">
        <span className="text-xs">top-k</span>
        {[20, 50, 100, 200].map((n) => (
          <button key={n} className={'btn ' + (k === n ? 'btn-primary' : 'btn-ghost')} onClick={() => setK(n)}>{n}</button>
        ))}
        <span className="text-xs ml-4">sort by</span>
        {['pagerank', 'betweenness', 'in_degree', 'out_degree'].map((s) => (
          <button key={s} className={'btn ' + (sort === s ? 'btn-primary' : 'btn-ghost')} onClick={() => setSort(s)}>{s}</button>
        ))}
        {loading && <span className="text-xs text-ink-100/60 ml-2">computing…</span>}
      </div>
      <div className="card scroll-area" style={{ maxHeight: 700 }}>
        <table className="tbl">
          <thead><tr>
            <th>#</th><th>type</th><th>id / name</th>
            <th>PageRank</th><th>Betweenness</th><th>in</th><th>out</th><th>actions</th>
          </tr></thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={r.id}>
                <td className="text-ink-100/50">{i + 1}</td>
                <td><span className="tag-kg">{r.type}</span></td>
                <td className="font-mono text-xs"><div>{r.id}</div><div className="text-ink-100/60">{r.name}</div></td>
                <td className="font-mono">{r.pagerank.toFixed(5)}</td>
                <td className="font-mono">{r.betweenness.toFixed(5)}</td>
                <td>{r.in_degree}</td>
                <td>{r.out_degree}</td>
                <td className="space-x-1 text-xs">
                  <Link className="btn-ghost text-xs" to={'/kg?id=' + r.id}>open</Link>
                  <Link className="btn-attack text-xs" to={'/pentest?target=' + encodeURIComponent(r.id)}>pentest</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
