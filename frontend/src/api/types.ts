export type UnitState = 'approved' | 'approved_moved' | 'changed' | 'partial' | 'removed' | 'new'
export type UnitFilter = 'all' | 'todo' | 'since_last'
export type DiffMode = 'base' | 'approved'
export type LineChange = 'context' | 'added' | 'removed'
export type ChangeType = 'added' | 'modified' | 'removed'
export type LineRange = [number, number]

export interface Reviewer {
  id: number
  email: string
  name: string
}

export interface Repo {
  id: number
  path: string
  name: string
  root_commit: string
  missing: boolean
}

export interface Refs {
  local: string[]
  remote: string[]
  default_base: string | null
}

export interface Revision {
  id: number
  number: number
  head_sha: string
  base_sha: string
  merge_base_sha: string
  created_at: string
}

export interface Review {
  id: number
  repo_id: number
  repo_path: string
  head_ref: string
  base_ref: string
  latest_revision: Revision | null
  counts: Record<UnitState, number>
  total: number
  approved: number
  open_threads: number
  total_threads: number
  last_session_at: string | null
  pull_request: ReviewPullRequest | null
}

export interface ReviewDetail extends Review {
  revisions: Revision[]
}

export interface Unit {
  id: number
  revision_id: number
  path: string
  old_path: string | null
  kind: string
  qualified_name: string
  state: UnitState
  change_type: ChangeType
  base_changed: boolean
  approval_id: string | null
  row_approvable: boolean
  rows_total: number
  rows_approved: number
  base_start: number | null
  base_end: number | null
  head_start: number | null
  head_end: number | null
  binary: boolean
  open_threads: number
  default_diff_mode: DiffMode
}

export interface DiffRow {
  change: LineChange
  old_index: number | null
  new_index: number | null
  old_line: number | null
  new_line: number | null
  text: string
  row_hash: string | null
  approved: boolean
  selection_id: string | null
  placeholder: boolean
}

export interface UnitDiff {
  unit_id: number
  mode: DiffMode
  available_modes: DiffMode[]
  approved_text_unavailable: boolean
  binary: boolean
  unified: string
  rows: DiffRow[]
}

export interface RefreshResult {
  revision: Revision
  created: boolean
  warning: string | null
}

export interface ApprovalRequest {
  unit_id?: number
  path?: string
  head_range?: LineRange | null
  base_range?: LineRange | null
}

export type ThreadScope = 'review' | 'file' | 'unit'
export type ThreadStatus = 'open' | 'resolved'
export type Side = 'head' | 'base'

export interface Comment {
  id: string
  thread_id: string
  author: Reviewer
  body: string
  created_at: string
  edited_at: string | null
  deleted: boolean
  mine: boolean
  remote_url: string | null
}

export interface ThreadAnchor {
  revision_id: number
  line_offset: number | null
  outdated: boolean
  unit_id: number | null
  file_line: number | null
  end_file_line: number | null
}

export interface Thread {
  id: string
  scope: ThreadScope
  path: string | null
  kind: string | null
  qualified_name: string | null
  side: Side | null
  status: ThreadStatus
  created_by: Reviewer
  created_at: string
  line_text: string | null
  line_count: number
  context_before: string[]
  context_after: string[]
  anchor: ThreadAnchor | null
  comments: Comment[]
  can_delete: boolean
}

export interface NewThreadRequest {
  scope: ThreadScope
  body: string
  unit_id?: number
  path?: string
  side?: Side
  line_offset?: number
  line_count?: number
}

export interface PullRequest {
  number: number
  title: string
  url: string
  head_sha: string
  head_ref: string
  base_ref: string
  author: string
  state: string
  is_draft: boolean
  updated_at: string
  comment_count: number
  unresolved_threads: number
  body: string
}

export interface PullRequestRow {
  pull: PullRequest
  review_id: number | null
}

export interface PullRequestList {
  status: { available: boolean; authenticated: boolean; message: string }
  repository: string | null
  pulls: PullRequestRow[]
}

export interface PullSyncResult {
  updated: number
  closed: number
  failed: string[]
}

export interface ReviewPullRequest {
  number: number
  title: string | null
  url: string | null
  author: string | null
  state: string | null
  description: string | null
}

export interface ForgeOverview {
  status: { available: boolean; authenticated: boolean; message: string }
  repository: string | null
  link: { provider: string; repository: string; pr_number: number } | null
  pull_request: PullRequest | null
  candidates: PullRequest[]
  pending_comments: number
  head_matches: boolean | null
  error: string | null
}

export interface PublishOutcome {
  comment_ids: string[]
  status: 'published' | 'updated' | 'skipped' | 'failed'
  detail: string
  url: string | null
}

export interface PublishResult {
  review_url: string | null
  outcomes: PublishOutcome[]
}

export interface DirectoryEntry {
  name: string
  path: string
  is_repo: boolean
}

export interface DirectoryListing {
  path: string
  parent: string | null
  home: string
  is_repo: boolean
  entries: DirectoryEntry[]
  truncated: boolean
}

export interface FoundRepository {
  name: string
  path: string
  registered: boolean
}

export interface RepositoryScan {
  root: string
  repositories: FoundRepository[]
  truncated: boolean
}
