import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

interface Props {
  /** Send a query into the shared chat conversation. */
  send: (query: string) => void
  streaming: boolean
}

/**
 * Global Cmd/Ctrl-K "Ask" entry point. Opens a centered input that feeds the
 * same chat send path as the side panel, so users can ask from anywhere.
 *
 * NOTE: this is a minimal modal; Phase B swaps it onto the Radix Dialog
 * primitive once the design-system layer lands.
 */
export function AskPalette({ send, streaming }: Props) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(o => !o)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) {
      setValue('')
      inputRef.current?.focus()
    }
  }, [open])

  const submit = () => {
    if (!value.trim() || streaming) return
    send(value)
    setOpen(false)
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="ask-overlay"
          onClick={() => setOpen(false)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <motion.div
            className="ask-palette"
            onClick={e => e.stopPropagation()}
            initial={{ opacity: 0, scale: 0.96, y: -12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -12 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
          >
            <input
              ref={inputRef}
              className="ask-input"
              placeholder="Ask about this codebase…"
              value={value}
              onChange={e => setValue(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') submit()
              }}
            />
            <div className="ask-hint">
              <kbd>Enter</kbd> to ask · <kbd>Esc</kbd> to close
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
