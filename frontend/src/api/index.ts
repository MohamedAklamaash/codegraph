import axios from 'axios'
import type { Repository, RepoFile, FileFn, GraphData, User, GitHubRepo, Citation } from '../types'

function readCookie(name: string): string {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[2]) : ''
}

export interface ChatStreamHandlers {
  onMeta?: (citations: Citation[]) => void
  onToken?: (text: string) => void
  onError?: (message: string) => void
  onDone?: () => void
}

// xsrf* config lets axios read the Django CSRF cookie and attach it as the
// header on same-origin unsafe requests — required because we use
// SessionAuthentication, not a token.
const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
})

http.interceptors.response.use(
  r => r,
  err => {
    if (err?.response?.status === 401 && !err.response?.data?.needs_reauth) {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
    return Promise.reject(err)
  },
)

export const api = {
  seedCsrf: () =>
    http.get('/auth/csrf/').then(() => undefined),

  getMe: () =>
    http.get<User>('/me/').then(r => r.data),

  startGithubLogin: () =>
    http.get<{ authorize_url: string }>('/auth/github/start/').then(r => {
      window.location.href = r.data.authorize_url
    }),

  logout: () =>
    http.post('/auth/logout/').then(() => undefined),

  listMyGithubRepos: (q?: string, page = 1) =>
    http.get<GitHubRepo[]>('/github/repos/', { params: { q, page } }).then(r => r.data),

  listRepos: () =>
    http.get<Repository[]>('/repos/').then(r => r.data),

  submitRepo: (url: string) =>
    http.post<Repository>('/repos/', { url }).then(r => r.data),

  attachRepo: (payload: { repo_id?: string; url?: string }) =>
    http.post<Repository>('/repos/attach/', payload).then(r => r.data),

  getRepo: (id: string) =>
    http.get<Repository>(`/repos/${id}/`).then(r => r.data),

  getFileTree: (repoId: string) =>
    http.get<{ files: RepoFile[] }>(`/files/${repoId}/tree/`).then(r => r.data.files),

  getFileFunctions: (repoId: string, fileId: number) =>
    http.get<FileFn[]>(`/files/${repoId}/files/${fileId}/functions/`).then(r => r.data),

  getGraph: (repoId: string, params?: { file_id?: number; node_id?: string; dir?: string; include_boilerplate?: boolean }) =>
    http.get<GraphData>(`/graph/${repoId}/`, { params }).then(r => r.data),

  traceNode: (repoId: string, nodeId: string) =>
    http.get<{
      name: string
      file: string
      start_line: number
      flow: { id: string; name: string; file: string; depth: number; parent_id: string | null }[]
      explanation: string
    }>(`/graph/${repoId}/trace/${nodeId}/`).then(r => r.data),

  // Streaming chat. Axios can't surface incremental bodies and EventSource is
  // GET-only (can't send the CSRF header), so we use fetch + ReadableStream and
  // parse the SSE frames by hand. The 401 -> auth:unauthorized dispatch is
  // replicated here because this path bypasses the axios interceptor.
  chatStream: async (
    repoId: string,
    query: string,
    handlers: ChatStreamHandlers,
    signal?: AbortSignal,
  ) => {
    const res = await fetch(`/api/chat/${repoId}/`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': readCookie('csrftoken'),
      },
      body: JSON.stringify({ query }),
      signal,
    })

    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      handlers.onError?.('Session expired. Please sign in again.')
      return
    }
    if (!res.ok || !res.body) {
      let message = 'Something went wrong.'
      try {
        message = (await res.json())?.error || message
      } catch { /* non-JSON error body */ }
      handlers.onError?.(message)
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const dispatch = (frame: string) => {
      const lines = frame.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) return
      let payload: Record<string, unknown>
      try { payload = JSON.parse(data) } catch { return }
      if (event === 'meta') handlers.onMeta?.(payload.functions as Citation[])
      else if (event === 'token') handlers.onToken?.(payload.text as string)
      else if (event === 'error') handlers.onError?.((payload.error as string) || 'Something went wrong.')
      else if (event === 'done') handlers.onDone?.()
    }

    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        dispatch(buffer.slice(0, idx))
        buffer = buffer.slice(idx + 2)
      }
    }
    if (buffer.trim()) dispatch(buffer)
  },
}
