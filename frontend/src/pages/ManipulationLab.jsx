import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function ManipulationLab() {
  const [recipes, setRecipes] = useState([])
  const [picked, setPicked] = useState(null)
  const [params, setParams] = useState({})
  const [log, setLog] = useState([])
  const [output, setOutput] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [snapLabel, setSnapLabel] = useState('pre-poison')
  const [exps, setExps] = useState([])
  const [eid, setEid] = useState('')

  const reload = () => {
    api.poison.recipes().then(setRecipes)
    api.poison.log().then(setLog)
    api.kg.snapshots().then(setSnapshots)
    api.experiments.list().then(setExps)
  }
  useEffect(reload, [])

  function pick(r) {
    setPicked(r)
    setParams(JSON.parse(JSON.stringify(r.params)))
  }

  async function run() {
    if (!picked) return
    const out = await api.poison.run(picked.id, params, eid ? +eid : null)
    setOutput(out)
    reload()
  }
  async function snap() {
    await api.kg.snapshot(snapLabel, 'before poison: ' + (picked?.id || '-'))
    reload()
  }
  async function cleanup() { await api.poison.cleanup(); reload() }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Manipulation Lab</h1>
        <p className="text-ink-100/60 text-sm">2024-26 톱티어 KG/RAG poisoning 6종 recipe. 실행 전 스냅샷 권장.</p>
      </div>

      <div className="card flex gap-2 flex-wrap items-center">
        <input className="input max-w-[240px]" value={snapLabel} onChange={(e) => setSnapLabel(e.target.value)} />
        <button className="btn-defense" onClick={snap}>📸 스냅샷</button>
        <button className="btn-attack" onClick={cleanup}>🧹 poison cleanup (모든 poison 노드 제거)</button>
        <select className="input max-w-[200px] ml-auto" value={eid} onChange={(e) => setEid(e.target.value)}>
          <option value="">(no experiment)</option>
          {exps.map((e) => <option key={e.id} value={e.id}>#{e.id} {e.title}</option>)}
        </select>
      </div>

      <div className="grid md:grid-cols-3 gap-3">
        {recipes.map((r) => (
          <div key={r.id}
               className={'card cursor-pointer transition ' + (picked?.id === r.id ? 'border-attack-500' : 'hover:border-attack-500/40')}
               onClick={() => pick(r)}>
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold">{r.title}</div>
                <div className="text-[11px] text-ink-100/60">{r.venue}</div>
              </div>
              <span className="tag-attack">{r.id}</span>
            </div>
            <div className="text-[11px] text-ink-100/60 mt-2">stealth band: {r.stealth_band[0]}–{r.stealth_band[1]}</div>
          </div>
        ))}
      </div>

      {picked && (
        <div className="card space-y-3">
          <div className="font-semibold">파라미터 — {picked.title}</div>
          {Object.entries(params).map(([k, v]) => (
            <div key={k} className="flex gap-2 items-center">
              <span className="text-xs text-ink-100/60 w-32">{k}</span>
              <input className="input" value={v} onChange={(e) => setParams({ ...params, [k]: e.target.value })} />
            </div>
          ))}
          <div className="flex gap-2">
            <button className="btn-attack" onClick={run}>☣ Inject Poison</button>
            <span className="text-xs text-ink-100/60 self-center">→ poison_log + nodes/edges 변경</span>
          </div>
          {output && (
            <div>
              <div className="text-xs text-ink-100/60">output</div>
              <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto">{JSON.stringify(output, null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <div className="font-semibold mb-2">Poison log</div>
          <table className="tbl"><thead><tr><th>id</th><th>recipe</th><th>target</th><th>stealth</th><th>ASR</th></tr></thead>
            <tbody>
              {log.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td><span className="tag-attack">{r.recipe}</span></td>
                  <td className="font-mono text-[11px]">{r.target_node}</td>
                  <td>{r.stealth_score?.toFixed?.(3)}</td>
                  <td className="text-attack-500">{r.asr?.toFixed?.(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="font-semibold mb-2">Snapshots</div>
          <table className="tbl"><thead><tr><th>id</th><th>label</th><th>nodes</th><th>edges</th><th /></tr></thead>
            <tbody>
              {snapshots.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.label}</td>
                  <td>{s.node_count}</td>
                  <td>{s.edge_count}</td>
                  <td><a href={'/snapshots'} className="text-kg-500 text-xs">→ diff/restore</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
