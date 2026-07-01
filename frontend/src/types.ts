export interface Row {
  [key: string]: unknown
}

export type ChartHint =
  | { type: 'bar' | 'line'; labelKey: string; valueKey: string }
  | { type: 'stat'; fields: string[] }

export type StreamEvent =
  | { type: 'sql'; sql: string; cached?: boolean }
  | { type: 'correcting'; sql: string; error: string }
  | { type: 'rows'; rows: Row[]; row_count: number }
  | { type: 'chart'; chart: ChartHint }
  | { type: 'explanation_delta'; text: string }
  | { type: 'followups'; questions: string[] }
  | { type: 'error'; error: string }
  | { type: 'done' }

export type MessageStatus = 'pending' | 'streaming' | 'done' | 'error'

export interface AssistantMessage {
  id: string
  role: 'assistant'
  status: MessageStatus
  sql?: string
  cached?: boolean
  rows?: Row[]
  rowCount?: number
  chart?: ChartHint | null
  explanation: string
  followups?: string[]
  error?: string
}

export interface UserMessage {
  id: string
  role: 'user'
  text: string
}

export type ChatMessage = UserMessage | AssistantMessage

export interface Chat {
  id: string
  title: string
  createdAt: number
  messages: ChatMessage[]
  datasetId: string
}

export interface DatasetColumn {
  name: string
  kind: 'numeric' | 'date' | 'categorical' | 'text'
}

export interface DatasetInfo {
  dataset_id: string
  name: string
  row_count: number
  columns: DatasetColumn[]
  example_questions: string[]
}

export type PaletteKey = 'indigo' | 'emerald' | 'violet' | 'amber' | 'rose'
export type ModeKey = 'light' | 'dark'

export interface ThemeState {
  palette: PaletteKey
  mode: ModeKey
}
