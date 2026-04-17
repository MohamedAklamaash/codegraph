import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, FileFn } from '../types'
import { api } from '../api'

const SUGGESTIONS = [
  'Where is authentication handled?',
  'What happens after login?',
  'Show DB-related functions',
]

interface Props {
  repoId: string
  onFocusFn: (fn: FileFn) => void
}

export function ChatPanel({ repoId, onFocusFn }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (query: string) => {
    if (!query.trim() || loading) return
    setInput('')
    setMessages(m => [...m, { role: 'user', content: query.trim() }])
    setLoading(true)
    try {
      const data = await api.chat(repoId, query.trim())
      setMessages(m => [...m, { role: 'assistant', content: data.answer, functions: data.functions }])
    } catch (err: unknown) {
      setMessages(m => [...m, { role: 'assistant', content: (err as { response?: { data?: { error?: string } } }).response?.data?.error || 'Something went wrong.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">Ask about the codebase</div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask anything about this repo</p>
            <ul>
              {SUGGESTIONS.map(s => <li key={s} onClick={() => send(s)}>{s}</li>)}
            </ul>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`msg msg-${msg.role}`}>
            <div className="msg-bubble">{msg.content}</div>
            {msg.functions && msg.functions.length > 0 && (
              <div className="msg-functions">
                {msg.functions.map(fn => (
                  <span key={fn.id} className="fn-tag" onClick={() => onFocusFn(fn)}>
                    {fn.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="msg msg-assistant">
            <div className="msg-bubble" style={{ color: 'var(--text-muted)' }}>Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="chat-input-row">
        <input
          type="text"
          placeholder="Ask a question…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send(input)}
          disabled={loading}
        />
        <button className="btn-send" onClick={() => send(input)} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
