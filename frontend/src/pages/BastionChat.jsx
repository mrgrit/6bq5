import { useState } from 'react'
import { api } from '../api.js'

export default function BastionChat() {
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)

  async function send() {
    if (!text.trim()) return
    const myMsg = { role: 'user', text }
    setMessages((m) => [...m, myMsg])
    setText(''); setBusy(true)
    try {
      const out = await api.bastion.chat(text)
      const reply = out?.data?.response || out?.data?.message || JSON.stringify(out.data)
      setMessages((m) => [...m, { role: 'agent', text: reply, source: out.source }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'agent', text: 'error: ' + e.message, source: 'err' }])
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div>
        <h1 className="text-2xl font-bold">Bastion Chat</h1>
        <p className="text-ink-100/60 text-sm">CCC bastion agent 와 대화. KG 사전 참조 + 사후 anchor 자동 (CLAUDE.md 정책).</p>
      </div>
      <div className="card flex-1 scroll-area space-y-2" style={{ minHeight: 400 }}>
        {messages.map((m, i) => (
          <div key={i} className={'p-2 rounded text-sm ' + (m.role === 'user' ? 'bg-kg-600/20 ml-12' : 'bg-ink-100/5 mr-12')}>
            <div className="text-[11px] text-ink-100/60 mb-1">{m.role}{m.source ? ' · ' + m.source : ''}</div>
            <div className="whitespace-pre-wrap">{m.text}</div>
          </div>
        ))}
      </div>
      <div className="card flex gap-2">
        <input className="input flex-1" placeholder="ask the agent…" value={text}
               onChange={(e) => setText(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && send()} />
        <button className="btn-primary" disabled={busy} onClick={send}>{busy ? '…' : 'send'}</button>
      </div>
    </div>
  )
}
