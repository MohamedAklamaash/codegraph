import axios from 'axios'
import type { Repository, RepoFile, FileFn, GraphData } from '../types'

const http = axios.create({ baseURL: '/api' })

export const api = {
  listRepos: () =>
    http.get<Repository[]>('/repos/').then(r => r.data),

  submitRepo: (url: string) =>
    http.post<Repository>('/repos/', { url }).then(r => r.data),

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
      flow: { id: string; name: string; file: string }[]
      explanation: string
    }>(`/graph/${repoId}/trace/${nodeId}/`).then(r => r.data),

  chat: (repoId: string, query: string) =>
    http.post<{ answer: string; functions: FileFn[] }>(`/chat/${repoId}/`, { query }).then(r => r.data),
}
