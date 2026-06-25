export type Theme = 'light' | 'dark'

const KEY = 'codegraph_theme'

export function getInitialTheme(): Theme {
  const saved = localStorage.getItem(KEY)
  return saved === 'light' ? 'light' : 'dark'
}

/** Apply a theme by toggling [data-theme] on <html> and notifying listeners. */
export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(KEY, theme)
  // The D3 graph reads CSS vars at draw time, so it must redraw on a swap.
  window.dispatchEvent(new CustomEvent('theme:change'))
}
