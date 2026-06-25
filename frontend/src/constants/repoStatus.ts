// Mirror of backend/apps/repos/models.py::RepoStatus. Keep keys in sync.
export const REPO_STATUSES = [
  { key: 'cloning', label: 'Cloning', description: 'Fetching repository from GitHub' },
  { key: 'parsing', label: 'Parsing', description: 'Extracting functions and call graph' },
  { key: 'embedding', label: 'Embedding', description: 'Generating semantic vectors' },
  { key: 'ready', label: 'Ready', description: 'Complete' },
] as const

export type RepoStatus = typeof REPO_STATUSES[number]['key'] | 'pending' | 'failed'
