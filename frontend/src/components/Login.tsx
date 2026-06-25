import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api'

const LANGS = ['Python', 'TypeScript', 'JavaScript', 'Go', 'Rust', 'Java', 'C / C++', 'Kotlin']

const FEATURES = [
  {
    title: 'Interactive call graph',
    body: 'Every function is a node, every call an edge. Pan, zoom, filter by file, and watch how execution actually flows — no more reading file-by-file.',
    icon: (
      <>
        <circle cx="6" cy="7" r="2.4" /><circle cx="18" cy="6" r="2.4" opacity="0.6" /><circle cx="12" cy="18" r="2.4" opacity="0.85" />
        <path d="M7.6 8.4 L10.8 16 M16.3 7.4 L13 16" strokeWidth="1.4" strokeLinecap="round" opacity="0.55" fill="none" />
      </>
    ),
  },
  {
    title: 'Ask your codebase',
    body: 'A semantic AI assistant grounded in your real functions. Answers cite actual code and jump straight to the node in the graph.',
    icon: (
      <>
        <path d="M4 5h16v11H9l-4 4v-4H4z" strokeWidth="1.6" fill="none" strokeLinejoin="round" />
        <path d="M8 9h8M8 12h5" strokeWidth="1.6" strokeLinecap="round" />
      </>
    ),
  },
  {
    title: 'Trace any flow',
    body: 'Follow a function’s full call chain across files in a single click. Understand dependencies and impact before you change a line.',
    icon: (
      <>
        <path d="M5 5v9a3 3 0 0 0 3 3h11" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        <path d="M15 13l4 4-4 4" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
  {
    title: 'Eight languages, zero setup',
    body: 'Point CodeGraph at any GitHub repo — public or private. We clone, parse, map, and index it automatically in seconds.',
    icon: (
      <>
        <path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13 5l-2 14" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
]

const STEPS = [
  { n: '01', title: 'Connect GitHub', body: 'Sign in and choose a repository — yours, your team’s, or any public project.' },
  { n: '02', title: 'We build the graph', body: 'CodeGraph extracts functions, maps call relationships, and embeds everything for semantic search.' },
  { n: '03', title: 'Explore & ask', body: 'Navigate the graph, trace execution flows, and ask questions in plain English.' },
]

function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden>
      <circle cx="5" cy="6" r="2.6" fill="currentColor" />
      <circle cx="18" cy="5" r="2.6" fill="currentColor" opacity="0.55" />
      <circle cx="12" cy="18" r="2.6" fill="currentColor" opacity="0.8" />
      <path d="M6.8 7.4 L10.8 16.2 M15.7 6.4 L12.8 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
    </svg>
  )
}

function GithubIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  )
}

function HeroGraphic() {
  const nodes = [
    { x: 70, y: 60 }, { x: 210, y: 40 }, { x: 300, y: 130 },
    { x: 150, y: 150 }, { x: 60, y: 200 }, { x: 250, y: 230 }, { x: 160, y: 270 },
  ]
  const edges = [[0, 3], [1, 2], [1, 3], [3, 4], [3, 5], [5, 6], [4, 6], [2, 5]]
  const colors = ['#6366f1', '#22d3ee', '#34d399', '#fbbf24', '#f472b6', '#a78bfa', '#38bdf8']
  return (
    <svg className="mk-graphic-svg" viewBox="0 0 360 320" fill="none">
      {edges.map(([a, b], i) => (
        <motion.line
          key={i}
          x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y}
          stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.4"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 0.9, delay: 0.2 + i * 0.06, ease: 'easeOut' }}
        />
      ))}
      {nodes.map((n, i) => (
        <motion.circle
          key={i}
          cx={n.x} cy={n.y} r={i === 3 ? 13 : 9}
          fill={colors[i % colors.length]}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.1 + i * 0.08, ease: 'backOut' }}
          style={{ transformOrigin: `${n.x}px ${n.y}px` }}
        />
      ))}
    </svg>
  )
}

export function Login() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('login_error') === '1') {
      setError('Sign in failed. Please try again.')
      params.delete('login_error')
      const next = params.toString()
      window.history.replaceState({}, '', window.location.pathname + (next ? `?${next}` : ''))
    }
  }, [])

  const signIn = async () => {
    setLoading(true)
    setError('')
    try {
      await api.startGithubLogin()
    } catch {
      setError('Could not start GitHub sign-in. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="marketing">
      <nav className="mk-nav">
        <div className="mk-brand"><span className="mk-brand-mark"><Logo /></span>CodeGraph</div>
        <button className="btn-ghost" onClick={signIn} disabled={loading}>Sign in</button>
      </nav>

      <header className="mk-hero">
        <div className="mk-hero-bg" />
        <motion.div
          className="mk-hero-copy"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          <span className="mk-eyebrow"><span className="mk-dot" /> AI-native code intelligence</span>
          <h1 className="mk-title">Understand any codebase<br /><span>in minutes, not weeks.</span></h1>
          <p className="mk-lede">
            CodeGraph turns any GitHub repository into an interactive, function-level
            knowledge graph — then lets you ask it anything. Onboard faster, review
            smarter, and ship with confidence.
          </p>
          <div className="mk-cta">
            <button className="btn-primary btn-github" onClick={signIn} disabled={loading}>
              <GithubIcon />
              {loading ? 'Redirecting…' : 'Sign in with GitHub'}
            </button>
            <span className="mk-cta-note">Free to start · Reads only the repos you choose</span>
          </div>
          {error && <p className="mk-error">{error}</p>}
          <div className="mk-langs">
            {LANGS.map(l => <span key={l} className="mk-lang">{l}</span>)}
          </div>
        </motion.div>
        <motion.div
          className="mk-hero-visual"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.15, ease: 'easeOut' }}
        >
          <div className="mk-card">
            <div className="mk-card-bar"><span /><span /><span /></div>
            <div className="mk-graphic"><HeroGraphic /></div>
          </div>
        </motion.div>
      </header>

      <section className="mk-section">
        <motion.div
          className="mk-section-head"
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.4 }}
        >
          <h2>Stop reading code line by line.</h2>
          <p>Everything you need to understand an unfamiliar codebase — in one view.</p>
        </motion.div>
        <div className="mk-features">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              className="mk-feature"
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.4, delay: i * 0.06 }}
            >
              <span className="mk-feature-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" stroke="currentColor">{f.icon}</svg>
              </span>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="mk-section mk-steps-section">
        <motion.div
          className="mk-section-head"
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.4 }}
        >
          <h2>From repo to insight in three steps.</h2>
        </motion.div>
        <div className="mk-steps">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.n}
              className="mk-step"
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
            >
              <span className="mk-step-n">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="mk-final">
        <div className="mk-final-glow" />
        <h2>See your codebase clearly.</h2>
        <p>Connect a repository and explore it as a living graph in under a minute.</p>
        <button className="btn-primary btn-github" onClick={signIn} disabled={loading}>
          <GithubIcon />
          {loading ? 'Redirecting…' : 'Sign in with GitHub'}
        </button>
      </section>

      <footer className="mk-footer">
        <div className="mk-brand"><span className="mk-brand-mark"><Logo size={18} /></span>CodeGraph</div>
        <span>Function-level code intelligence · We request the <code>repo</code> scope to clone the private repositories you choose.</span>
      </footer>
    </div>
  )
}
