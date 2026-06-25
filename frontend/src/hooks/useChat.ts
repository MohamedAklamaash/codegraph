import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../types'
import { api } from '../api'

/**
 * Owns chat state + the streaming send path for a repo. Lifted out of ChatPanel
 * so multiple surfaces (the right-rail panel and the Cmd/Ctrl-K palette) can
 * share one conversation and one send path.
 */
export function useChat(repoId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  // Reset the conversation when the active repo changes, and abort any
  // in-flight stream so its tokens don't bleed into the next repo.
  useEffect(() => {
    abortRef.current?.abort()
    setMessages([])
    setStreaming(false)
  }, [repoId])

  useEffect(() => () => abortRef.current?.abort(), [])

  // Mutate the trailing assistant placeholder as tokens/meta arrive.
  const patchLast = useCallback((patch: (m: ChatMessage) => ChatMessage) => {
    setMessages(prev => {
      if (prev.length === 0) return prev
      const copy = [...prev]
      copy[copy.length - 1] = patch(copy[copy.length - 1])
      return copy
    })
  }, [])

  const send = useCallback((raw: string) => {
    const query = raw.trim()
    if (!query || streaming) return

    setMessages(m => [
      ...m,
      { role: 'user', content: query },
      { role: 'assistant', content: '' },
    ])
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    api.chatStream(
      repoId,
      query,
      {
        onMeta: citations => patchLast(m => ({ ...m, citations })),
        onToken: text => patchLast(m => ({ ...m, content: m.content + text })),
        onError: message =>
          patchLast(m => ({ ...m, content: m.content || message })),
        onDone: () => setStreaming(false),
      },
      controller.signal,
    ).catch(() => {
      patchLast(m => ({ ...m, content: m.content || 'Something went wrong.' }))
      setStreaming(false)
    }).finally(() => setStreaming(false))
  }, [repoId, streaming, patchLast])

  return { messages, streaming, send }
}
