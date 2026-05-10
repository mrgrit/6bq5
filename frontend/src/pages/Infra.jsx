import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Infra() {
  const [status, setStatus] = useState(null)
  const [logs, setLogs] = useState('')
  const [pickedSvc, setPickedSvc] = useState('attacker')
  const [cmd, setCmd] = useState('uname -a')
  const [out, setOut] = useState(null)
  const [history, setHistory] = useState([])

  const reload = () => {
    api.infra.status().then(setStatus)
    api.infra.history().then(setHistory)
  }
  useEffect(reload, [])

  async function up() { await api.infra.up(); reload() }
  async function down() { if (confirm('docker compose down?')) { await api.infra.down(); reload() } }
  async function restart(s) { await api.infra.restart(s); reload() }
  async function pull() { setLogs((await api.infra.logs(pickedSvc, 200)).stdout || '(no log)') }
  async function exec() { setOut(await api.infra.exec(pickedSvc, cmd)) }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">6v6 Console</h1>
        <p className="text-ink-100/60 text-sm">/home/opsclaw/6v6 docker-compose 조작. attacker / fw / web / bastion / siem 컨테이너 접근.</p>
      </div>

      <div className="card flex gap-2">
        <button className="btn-defense" onClick={up}>compose up -d</button>
        <button className="btn-attack" onClick={down}>compose down</button>
        <button className="btn-ghost" onClick={reload}>↻ refresh</button>
        <span className="ml-auto text-xs text-ink-100/60">{status?.infra_dir}</span>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <div className="font-semibold mb-2">서비스</div>
          <table className="tbl"><thead><tr><th>name</th><th>state</th><th /></tr></thead>
            <tbody>
              {(status?.services || []).map((s, i) => {
                const name = s.Name || s.Service || s.name || JSON.stringify(s).slice(0, 40)
                const state = s.State || s.state || ''
                return (
                  <tr key={i}>
                    <td className="font-mono text-xs">{name}</td>
                    <td><span className={'tag ' + (state === 'running' ? 'bg-defense-600/30 text-defense-500' : 'bg-attack-600/30 text-attack-500')}>{state}</span></td>
                    <td><button className="text-xs text-kg-500" onClick={() => restart(s.Service || name)}>restart</button></td>
                  </tr>
                )
              })}
              {!status?.services?.length && <tr><td colSpan={3} className="text-xs text-ink-100/50">No containers up. compose up -d to start.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="card space-y-2">
          <div className="font-semibold">실행 / 로그</div>
          <div className="flex gap-2">
            <select className="input max-w-[150px]" value={pickedSvc} onChange={(e) => setPickedSvc(e.target.value)}>
              <option>attacker</option><option>bastion</option><option>fw</option><option>ips</option><option>web</option><option>siem</option><option>juice</option>
            </select>
            <input className="input flex-1 font-mono" value={cmd} onChange={(e) => setCmd(e.target.value)} />
            <button className="btn-attack" onClick={exec}>exec</button>
            <button className="btn-ghost" onClick={pull}>logs</button>
          </div>
          {out && (
            <pre className="bg-ink-950 p-2 rounded text-xs overflow-auto" style={{ maxHeight: 200 }}>{(out.stdout || '') + (out.stderr ? '\n[stderr] ' + out.stderr : '')}</pre>
          )}
          {logs && (
            <pre className="bg-ink-950 p-2 rounded text-[11px] overflow-auto" style={{ maxHeight: 250 }}>{logs}</pre>
          )}
        </div>
      </div>

      <div className="card scroll-area" style={{ maxHeight: 300 }}>
        <div className="font-semibold mb-2">infra event log</div>
        <table className="tbl"><thead><tr><th>ts</th><th>host</th><th>op</th><th>status</th><th>output</th></tr></thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id}>
                <td className="text-[11px]">{h.created_at}</td>
                <td className="text-[11px]">{h.host}</td>
                <td><span className="tag">{h.op}</span></td>
                <td>{h.status === 'ok' ? '✓' : <span className="text-attack-500">✗</span>}</td>
                <td className="text-[11px] text-ink-100/70 max-w-[400px] truncate">{h.output}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
