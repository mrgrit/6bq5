import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'

const COLORS = ['#6366f1', '#22d3ee', '#10b981', '#facc15', '#f97316', '#ef4444', '#a855f7', '#ec4899', '#14b8a6', '#84cc16', '#fb7185']

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.kg.stats().then(setStats).catch((e) => setErr(e.message))
    api.health().then(setHealth).catch(() => {})
  }, [])

  if (err) return <div className="text-attack-500">err: {err}</div>
  if (!stats) return <div>loading…</div>

  const nodeData = Object.entries(stats.node_counts).map(([k, v]) => ({ name: k, value: v }))
  const edgeData = Object.entries(stats.edge_counts).map(([k, v]) => ({ name: k, value: v }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">대시보드</h1>
        <p className="text-ink-100/60 text-sm">
          CCC Knowledge Graph (precinct6 제외) 위에서 변조 위험성 실험 → 모의해킹 → 보호 체계 개발
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="총 노드" v={stats.total_nodes} link="/kg" tone="kg" />
        <Stat label="총 엣지" v={stats.total_edges} link="/graph" tone="kg" />
        <Stat label="앵커 (history)" v={stats.total_anchors} link="/kg" tone="kg" />
        <Stat label="실험" v={stats.experiments} link="/manipulate" tone="attack" />
        <Stat label="방어 알람" v={stats.alerts} link="/defense" tone="defense" />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="font-semibold mb-2 text-ink-100/80">노드 타입 분포</h3>
          <div style={{ height: 250 }}>
            <ResponsiveContainer>
              <BarChart data={nodeData}>
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip contentStyle={{ background: '#0b1020', border: '1px solid #334' }} />
                <Bar dataKey="value" fill="#6366f1" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-2 text-ink-100/80">엣지 타입 분포</h3>
          <div style={{ height: 250 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={edgeData} dataKey="value" nameKey="name" outerRadius={90} label>
                  {edgeData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#0b1020', border: '1px solid #334' }} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="font-semibold mb-2 text-ink-100/80">최근 KG 변경</h3>
          <table className="tbl">
            <thead><tr><th>type</th><th>name</th><th>updated</th></tr></thead>
            <tbody>
              {stats.recent.map((r) => (
                <tr key={r.id}>
                  <td><span className="tag-kg">{r.type}</span></td>
                  <td className="font-mono text-xs"><Link className="hover:text-kg-500" to={'/kg?id=' + r.id}>{r.name}</Link></td>
                  <td className="text-xs text-ink-100/60">{r.updated_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-2 text-ink-100/80">서비스 헬스</h3>
          <pre className="text-xs text-ink-100/70 whitespace-pre-wrap">
{health ? JSON.stringify(health, null, 2) : 'checking…'}
          </pre>
          <div className="mt-3 text-xs text-ink-100/60">
            · LLM 미연결 시 mock 응답 — 기능은 동작<br/>
            · Bastion 미연결 시 LLM fallback 사용
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-2 text-ink-100/80">실험 워크플로우</h3>
        <div className="grid md:grid-cols-3 gap-3 text-sm">
          <Step n={1} title="변조 (Manipulation)" desc="6개 recipe 중 선택, 타겟 노드 + 파라미터 → KG 주입" link="/manipulate" tone="attack" />
          <Step n={2} title="모의해킹 (Pentest)" desc="가치 매트릭스 → 타겟 식별 → LLM 공격 plan → 6v6 attacker 실행" link="/pentest" tone="attack" />
          <Step n={3} title="방어 (Defense)" desc="FOL · centrality spike · 인증 robustness · 분포 거리" link="/defense" tone="defense" />
        </div>
      </div>
    </div>
  )
}

function Stat({ label, v, link, tone = 'kg' }) {
  return (
    <Link to={link || '#'} className={'card hover:border-' + tone + '-500/50 transition'}>
      <div className="text-[11px] uppercase text-ink-100/60">{label}</div>
      <div className="text-2xl font-bold mt-1">{(v ?? 0).toLocaleString()}</div>
    </Link>
  )
}

function Step({ n, title, desc, link, tone }) {
  return (
    <Link to={link} className="card block hover:border-kg-500/50">
      <div className="flex items-center gap-2 mb-1">
        <span className={'w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold bg-' + tone + '-600/30 text-' + tone + '-500'}>{n}</span>
        <span className="font-semibold">{title}</span>
      </div>
      <div className="text-xs text-ink-100/70">{desc}</div>
    </Link>
  )
}
