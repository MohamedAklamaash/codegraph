import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../types'

const SUGGESTIONS = [
  'Where is authentication handled?',
  'What happens after login?',
  'Show DB-related functions',
]

interface Props {
  messages: ChatMessage[]
  streaming: boolean
  send: (query: string) => void
  /** Focus/center a cited function in the graph by its node id. */
  onCiteNode: (nodeId: string) => void
}

export function ChatPanel({ messages, streaming, send, onCiteNode }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = (query: string) => {
    if (!query.trim() || streaming) return
    send(query)
    setInput('')
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask anything about this repo</p>
            <ul>
              {SUGGESTIONS.map(s => <li key={s} onClick={() => submit(s)}>{s}</li>)}
            </ul>
          </div>
        )}
        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1
          const pending = msg.role === 'assistant' && !msg.content && streaming && isLast
          return (
            <motion.div
              key={i}
              className={`msg msg-${msg.role}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
            >
              <div className="msg-bubble">
                {pending ? (
                  <span className="msg-pending">Thinking…</span>
                ) : msg.role === 'assistant' ? (
                  <div className="md">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  msg.content
                )}
              </div>

              {msg.citations && msg.citations.length > 0 && (
                <div className="msg-functions">
                  {msg.citations.map(c => (
                    <button
                      key={c.id}
                      className="fn-tag"
                      title={`${c.file}:${c.start_line}`}
                      onClick={() => onCiteNode(c.node_id)}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              )}
            </motion.div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <input
          type="text"
          placeholder="Ask a question…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit(input)}
          disabled={streaming}
        />
        <button className="btn-send" onClick={() => submit(input)} disabled={streaming || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
