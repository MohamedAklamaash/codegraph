import axios from 'axios'
import type { Repository, RepoFile, FileFn, GraphData, User, GitHubRepo } from '../types'

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
    if (err?.response?.status === 401) {
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

  getGraph: (repoId: string, params?: { file_id?: number; node_id?: string; dir?: string }) =>
    http.get<GraphData>(`/graph/${repoId}/`, { params }).then(r => r.data),

  traceNode: (repoId: string, nodeId: string) =>
    http.get<{
      name: string
      file: string
      start_line: number
      flow: { id: string; name: string; file: string; depth: number; parent_id: string | null }[]
      explanation: string
    }>(`/graph/${repoId}/trace/${nodeId}/`).then(r => r.data),

  chat: (repoId: string, query: string) =>
    http.post<{ answer: string; functions: FileFn[] }>(`/chat/${repoId}/`, { query }).then(r => r.data),
}
