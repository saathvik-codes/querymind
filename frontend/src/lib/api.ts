import type { DatasetInfo, StreamEvent } from '../types'

// In dev, Vite's proxy (vite.config.ts) forwards /api -> localhost:8030.
// In a static production build there's no dev server to proxy for us, so
// VITE_API_URL must point straight at the deployed backend (e.g. Render).
const API = import.meta.env.VITE_API_URL || '/api'

/**
 * The backend uses a plain `StreamingResponse` (not EventSource-compatible,
 * since it's a POST with a body), so we parse the `data: {...}\n\n` framing
 * ourselves off a fetch ReadableStream instead of using the EventSource API.
 */
export async function streamQuery(
  question: string,
  datasetId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API}/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, dataset_id: datasetId }),
    signal,
  })

  if (!res.ok || !res.body) {
    throw new Error(`Request failed (${res.status})`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const line = chunk.trim()
      if (!line.startsWith('data:')) continue
      const payload = line.slice(5).trim()
      if (!payload) continue
      try {
        onEvent(JSON.parse(payload) as StreamEvent)
      } catch {
        // ignore a partial/malformed frame rather than killing the whole stream
      }
    }
  }
}

export async function fetchDatasets(): Promise<DatasetInfo[]> {
  const res = await fetch(`${API}/datasets`)
  if (!res.ok) throw new Error(`Failed to load datasets (${res.status})`)
  const data = await res.json()
  return data.datasets as DatasetInfo[]
}

export async function uploadDataset(file: File): Promise<DatasetInfo> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API}/datasets/upload`, { method: 'POST', body: formData })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || `Upload failed (${res.status})`)
  }
  return (await res.json()) as DatasetInfo
}
