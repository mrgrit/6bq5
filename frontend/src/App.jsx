import { NavLink, Route, Routes, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import KgExplorer from './pages/KgExplorer.jsx'
import GraphView from './pages/GraphView.jsx'
import ValueMatrix from './pages/ValueMatrix.jsx'
import ManipulationLab from './pages/ManipulationLab.jsx'
import Pentest from './pages/Pentest.jsx'
import Defense from './pages/Defense.jsx'
import Experiments from './pages/Experiments.jsx'
import RagTrace from './pages/RagTrace.jsx'
import MemoryTrace from './pages/MemoryTrace.jsx'
import Infra from './pages/Infra.jsx'
import BastionChat from './pages/BastionChat.jsx'
import Notes from './pages/Notes.jsx'
import Snapshots from './pages/Snapshots.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '◎', group: 'Core' },
  { to: '/kg', label: 'KG Explorer', icon: '⌘', group: 'KG' },
  { to: '/graph', label: 'Graph View', icon: '◇', group: 'KG' },
  { to: '/matrix', label: 'Value Matrix', icon: '▣', group: 'KG' },
  { to: '/snapshots', label: 'Snapshots', icon: '⊞', group: 'KG' },
  { to: '/manipulate', label: 'Manipulation Lab', icon: '☣', group: 'Attack' },
  { to: '/pentest', label: 'Pentest Workbench', icon: '⚔', group: 'Attack' },
  { to: '/rag', label: 'RAG Trace', icon: '↪', group: 'Attack' },
  { to: '/memory', label: 'Memory Trace', icon: '⌥', group: 'Attack' },
  { to: '/defense', label: 'Defense Studio', icon: '⛨', group: 'Defense' },
  { to: '/infra', label: '6v6 Console', icon: '⚙', group: 'Ops' },
  { to: '/bastion', label: 'Bastion Chat', icon: '◴', group: 'Ops' },
  { to: '/notes', label: 'Journal / Notes', icon: '✎', group: 'Ops' },
]

const groupOrder = ['Core', 'KG', 'Attack', 'Defense', 'Ops']

export default function App() {
  return (
    <div className="h-full flex">
      <aside className="w-60 bg-ink-900 border-r border-ink-100/10 p-3 overflow-y-auto">
        <div className="text-xl font-bold mb-1 text-kg-500">6bq5</div>
        <div className="text-[11px] text-ink-100/60 mb-4">
          KG Manipulation · Targeted Pentest · Defense
        </div>
        {groupOrder.map((g) => (
          <div key={g} className="mb-3">
            <div className="text-[10px] uppercase tracking-wider text-ink-100/50 px-2 mb-1">{g}</div>
            {NAV.filter((n) => n.group === g).map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === '/'}
                className={({ isActive }) =>
                  'flex items-center gap-2 px-2 py-1.5 rounded text-sm ' +
                  (isActive ? 'bg-kg-600/20 text-kg-500' : 'text-ink-100/80 hover:bg-ink-100/5')
                }
              >
                <span className="w-4 text-center">{n.icon}</span>
                <span>{n.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
        <div className="mt-6 text-[10px] text-ink-100/40 px-2">
          KG: CCC sanitized · attacker: 6v6 · agent: bastion
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/kg" element={<KgExplorer />} />
          <Route path="/graph" element={<GraphView />} />
          <Route path="/matrix" element={<ValueMatrix />} />
          <Route path="/snapshots" element={<Snapshots />} />
          <Route path="/manipulate" element={<ManipulationLab />} />
          <Route path="/pentest" element={<Pentest />} />
          <Route path="/rag" element={<RagTrace />} />
          <Route path="/memory" element={<MemoryTrace />} />
          <Route path="/defense" element={<Defense />} />
          <Route path="/infra" element={<Infra />} />
          <Route path="/bastion" element={<BastionChat />} />
          <Route path="/notes" element={<Notes />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  )
}
