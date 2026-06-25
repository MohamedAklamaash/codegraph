import { useState } from 'react'
import { applyTheme, getInitialTheme, type Theme } from '../theme'

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme())

  const toggle = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    applyTheme(next)
  }

  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      aria-label="Toggle color theme"
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
