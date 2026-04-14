export interface Repository {
  id: string
  url: string
  name: string
  status: 'pending' | 'cloning' | 'parsing' | 'graphing' | 'embedding' | 'ready' | 'failed'
  status_message: string
  created_at: string
}

export interface RepoFile {
  id: number
  path: string
  language: string
}

export interface FunctionNode {
  id: string
  name: string
  file: string
  file_id: number
  start_line: number
  summary: string
}

export interface FunctionEdge {
  id: string
  source: string
  target: string
  type: 'CALLS' | 'IMPORTS'
}

export interface GraphData {
  nodes: FunctionNode[]
  edges: FunctionEdge[]
}

export interface FileFn {
  id: number
  name: string
  start_line: number
  end_line: number
  summary: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  functions?: FileFn[]
}
