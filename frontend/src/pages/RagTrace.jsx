import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function RagTrace() {
  const [query, setQuery] = useState('이 인프라에서 가장 위험한 자산은?')
  const [picked, setPicked] = useState([])
  const [search, setSearch] = useState('host')
  const [matches, setMatches] = useState([])
  const [poisoned, setPoisoned] = useState(false)
  const [eid, setEid] = useState('')
  const [exps, setExps] = useState([])
  const [traces, setTraces] = useState([])
  const [busy, setBusy] = useState(false)

  const reload = () => {
    api.experiments.list().then(setExps)
    api.rag.list().then(setTraces)
  }
  useEffect(reload, [])

  async function runSearch() { setMatches(await api.kg.search(search)) }
  function pick(n) { setPicked((p) => p.includes(n.id) ? p : [...p, n.id]) }
  function unpick(id) { setPicked((p) => p.filter((x) => x !== id)) }

  async function run() {
    setBusy(true)
    try {
      await api.rag.trace(query, picked, poisoned, eid ? +eid : null)
      reload()
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">RAG Trace Replay</h1>
        <p className="text-ink-100/60 text-sm">PoisonedRAG (USENIX'25), One-Shot-Dominance (EMNLP'25) 영향 attribution. KG 노드를 retrieved chunk 로 붙여 LLM에 답 생성 → 기록.</p>
      </div>

      <div className="card space-y-2">
        <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="question" />
        <div className="flex gap-2">
          <input className="input flex-1" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="search KG to add chunks" />
          <button className="btn-ghost" onClick={runSearch}>search</button>
        </div>
        <div className="grid md:grid-cols-2 gap-2">
          <div>
            <div className="text-xs text-ink-100/60">검색 결과</div>
            <div className="space-y-1 scroll-area" style={{ maxHeight: 200 }}>
              {matches.map((n) => (
                <div key={n.id} className="bg-ink-950 p-1 rounded flex justify-between items-center">
                  <span className="text-xs font-mono truncate">{n.id} — {n.name}</span>
                  <button className="btn-ghost text-xs" onClick={() => pick(n)}>+</button>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-ink-100/60">retrieved ({picked.length})</div>
            <div className="space-y-1 scroll-area" style={{ maxHeight: 200 }}>
              {picked.map((id) => (
                <div key={id} className="bg-ink-950 p-1 rounded flex justify-between items-center">
                  <span className="text-xs font-mono truncate">{id}</span>
                  <button className="btn-ghost text-xs" onClick={() => unpick(id)}>×</button>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={poisoned} onChange={(e) => setPoisoned(e.target.checked)} /> poisoned context (라벨)</label>
          <select className="input max-w-[200px] ml-auto" value={eid} onChange={(e) => setEid(e.target.value)}>
            <option value="">(no experiment)</option>
            {exps.map((e) => <option key={e.id} value={e.id}>#{e.id} {e.title}</option>)}
          </select>
          <button className="btn-attack" disabled={busy} onClick={run}>{busy ? 'generating…' : 'generate answer'}</button>
        </div>
      </div>

      <div className="card scroll-area" style={{ maxHeight: 500 }}>
        <div className="font-semibold mb-2">trace history</div>
        {traces.map((t) => (
          <div key={t.id} className="bg-ink-950 p-2 rounded mb-2 text-xs">
            <div className="flex gap-2 items-center mb-1">
              <span className={t.poisoned ? 'tag-attack' : 'tag-defense'}>{t.poisoned ? 'poisoned' : 'clean'}</span>
              <span className="text-ink-100/60">#{t.id} · {t.created_at}</span>
            </div>
            <div className="font-mono text-[11px] mb-1">Q: {t.query}</div>
            <div className="text-ink-100/60 mb-1">retrieved: {t.retrieved}</div>
            <div className="whitespace-pre-wrap">A: {t.generation}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
