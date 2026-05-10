import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Defense() {
  const [rules, setRules] = useState([])
  const [alerts, setAlerts] = useState([])
  const [scanResult, setScanResult] = useState(null)
  const [editing, setEditing] = useState(null)
  const [certInput, setCertInput] = useState('asset:host:web')
  const [certResult, setCertResult] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [pickedSnap, setPickedSnap] = useState(null)
  const [distResult, setDistResult] = useState(null)

  const reload = () => {
    api.defense.rules().then(setRules)
    api.defense.alerts().then(setAlerts)
    api.kg.snapshots().then(setSnapshots)
  }
  useEffect(reload, [])

  async function runFull() {
    setScanResult(await api.defense.scanFull())
    api.defense.alerts().then(setAlerts)
  }
  async function checkCert() { setCertResult(await api.defense.cert(certInput)) }
  async function checkDist() { if (pickedSnap) setDistResult(await api.defense.distribution(pickedSnap)) }
  async function saveRule() {
    await api.defense.upsert(editing); setEditing(null); reload()
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Defense Studio</h1>
        <p className="text-ink-100/60 text-sm">FOL · centrality spike (DShield NDSS'25) · certified radius (AGNNCert USENIX'25) · dist distance (DPSBA NeurIPS'25)</p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <div className="flex justify-between items-center mb-2">
            <div className="font-semibold">방어 규칙</div>
            <button className="btn-defense" onClick={() => setEditing({ name: '', kind: 'fol', body: '', enabled: 1 })}>+ 새 규칙</button>
          </div>
          <table className="tbl"><thead><tr><th>kind</th><th>name</th><th>body</th><th>on</th><th /></tr></thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id}>
                  <td><span className="tag">{r.kind}</span></td>
                  <td>{r.name}</td>
                  <td className="text-[11px] text-ink-100/70 max-w-[200px] truncate">{r.body}</td>
                  <td>{r.enabled ? '✓' : ''}</td>
                  <td className="space-x-1 text-xs">
                    <button onClick={() => setEditing(r)}>edit</button>
                    <button className="text-attack-500" onClick={async () => { await api.defense.remove(r.id); reload() }}>del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="flex justify-between items-center mb-2">
            <div className="font-semibold">실행</div>
            <button className="btn-defense" onClick={runFull}>⛨ run all detectors</button>
          </div>
          <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 300 }}>
{scanResult ? JSON.stringify(scanResult, null, 2) : 'no scan yet'}
          </pre>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="card">
          <div className="font-semibold mb-2">Certified robustness (AGNNCert)</div>
          <div className="flex gap-2 mb-2">
            <input className="input" value={certInput} onChange={(e) => setCertInput(e.target.value)} />
            <button className="btn-defense" onClick={checkCert}>cert</button>
          </div>
          {certResult && <pre className="text-[11px] bg-ink-950 p-2 rounded">{JSON.stringify(certResult, null, 2)}</pre>}
        </div>

        <div className="card">
          <div className="font-semibold mb-2">Distribution distance (DPSBA stealth)</div>
          <div className="flex gap-2 mb-2">
            <select className="input" value={pickedSnap || ''} onChange={(e) => setPickedSnap(+e.target.value)}>
              <option value="">snapshot…</option>
              {snapshots.map((s) => <option key={s.id} value={s.id}>#{s.id} {s.label}</option>)}
            </select>
            <button className="btn-defense" onClick={checkDist}>diff</button>
          </div>
          {distResult && <pre className="text-[11px] bg-ink-950 p-2 rounded">{JSON.stringify(distResult, null, 2)}</pre>}
        </div>

        <div className="card">
          <div className="font-semibold mb-2">최근 alerts ({alerts.length})</div>
          <div className="scroll-area" style={{ maxHeight: 240 }}>
            <table className="tbl"><thead><tr><th>sev</th><th>target</th><th>msg</th></tr></thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td><span className={'tag ' + (a.severity === 'high' ? 'bg-attack-600/30 text-attack-500' : 'bg-ink-100/10')}>{a.severity}</span></td>
                    <td className="text-xs font-mono">{a.target}</td>
                    <td className="text-xs">{a.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setEditing(null)}>
          <div className="card w-[600px]" onClick={(e) => e.stopPropagation()}>
            <div className="text-lg font-semibold mb-2">규칙 편집</div>
            <input className="input mb-2" placeholder="name" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            <select className="input mb-2" value={editing.kind} onChange={(e) => setEditing({ ...editing, kind: e.target.value })}>
              <option>fol</option><option>anomaly</option><option>centrality</option><option>embedding</option>
            </select>
            <textarea className="input font-mono text-xs" rows={6} value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} />
            <label className="text-xs flex items-center gap-1 mt-2"><input type="checkbox" checked={!!editing.enabled} onChange={(e) => setEditing({ ...editing, enabled: e.target.checked ? 1 : 0 })} /> enabled</label>
            <div className="flex gap-2 justify-end mt-2">
              <button className="btn-ghost" onClick={() => setEditing(null)}>cancel</button>
              <button className="btn-defense" onClick={saveRule}>save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
