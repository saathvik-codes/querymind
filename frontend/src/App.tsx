import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import Sidebar from './components/Sidebar'
import { UserBubble, AssistantBubble } from './components/MessageBubble'
import OnboardingTour from './components/OnboardingTour'
import DatasetBar from './components/DatasetBar'
import { streamQuery, fetchDatasets, uploadDataset } from './lib/api'
import { loadChats, saveChats, loadTheme, saveTheme, hasSeenOnboarding, setSeenOnboarding } from './lib/storage'
import type { AssistantMessage, Chat, DatasetInfo, ThemeState } from './types'

const DEFAULT_DATASET: DatasetInfo = {
  dataset_id: 'default',
  name: 'UK Online Retail (2009–2011)',
  row_count: 1_041_670,
  columns: [],
  example_questions: [],
}

const EXAMPLE_CATEGORIES: { label: string; questions: string[] }[] = [
  {
    label: 'Revenue',
    questions: ['Which country generated the most revenue?', 'Which month had the highest revenue?'],
  },
  {
    label: 'Products',
    questions: ['Top 5 products by total revenue?', 'Products with more than 10,000 total units sold?'],
  },
  {
    label: 'Customers',
    questions: ['How many unique customers each month in 2011?', 'Average order value by country?'],
  },
]

function newId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function makeTitle(text: string): string {
  const trimmed = text.trim()
  return trimmed.length > 42 ? trimmed.slice(0, 42) + '…' : trimmed
}

export default function App() {
  const [chats, setChats] = useState<Chat[]>(() =>
    loadChats().map((c) => ({ ...c, datasetId: c.datasetId ?? 'default' })),
  )
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [datasets, setDatasets] = useState<DatasetInfo[]>([DEFAULT_DATASET])
  const [activeDatasetId, setActiveDatasetId] = useState('default')
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [theme, setTheme] = useState<ThemeState>(() => loadTheme())
  const [showOnboarding, setShowOnboarding] = useState(() => !hasSeenOnboarding())
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    saveChats(chats)
  }, [chats])

  useEffect(() => {
    saveTheme(theme)
    document.documentElement.setAttribute('data-palette', theme.palette)
    document.documentElement.setAttribute('data-mode', theme.mode)
  }, [theme])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [chats, activeChatId])

  useEffect(() => {
    fetchDatasets()
      .then((list) => {
        if (list.length > 0) setDatasets(list)
      })
      .catch(() => {
        // backend not reachable yet — keep the default dataset placeholder
      })
  }, [])

  const activeChat = chats.find((c) => c.id === activeChatId) ?? null
  const selectedDataset = datasets.find((d) => d.dataset_id === activeDatasetId) ?? DEFAULT_DATASET

  function updateChat(chatId: string, updater: (chat: Chat) => Chat) {
    setChats((prev) => prev.map((c) => (c.id === chatId ? updater(c) : c)))
  }

  function updateLastAssistant(chatId: string, patch: Partial<AssistantMessage> | ((m: AssistantMessage) => Partial<AssistantMessage>)) {
    updateChat(chatId, (chat) => {
      const messages = [...chat.messages]
      const lastIdx = messages.length - 1
      const last = messages[lastIdx]
      if (!last || last.role !== 'assistant') return chat
      const p = typeof patch === 'function' ? patch(last) : patch
      messages[lastIdx] = { ...last, ...p }
      return { ...chat, messages }
    })
  }

  async function submit(question: string) {
    const text = question.trim()
    if (!text || sending) return
    setSending(true)
    setInput('')

    let chatId = activeChatId
    const datasetId = activeChat ? activeChat.datasetId : activeDatasetId
    const userMsg = { id: newId(), role: 'user' as const, text }
    const assistantMsg: AssistantMessage = {
      id: newId(),
      role: 'assistant',
      status: 'pending',
      explanation: '',
    }

    if (!chatId) {
      chatId = newId()
      const chat: Chat = {
        id: chatId,
        title: makeTitle(text),
        createdAt: Date.now(),
        messages: [userMsg, assistantMsg],
        datasetId,
      }
      setChats((prev) => [...prev, chat])
      setActiveChatId(chatId)
    } else {
      updateChat(chatId, (chat) => ({ ...chat, messages: [...chat.messages, userMsg, assistantMsg] }))
    }

    const targetChatId = chatId
    try {
      await streamQuery(text, datasetId, (event) => {
        switch (event.type) {
          case 'sql':
            updateLastAssistant(targetChatId, { sql: event.sql, cached: event.cached, status: 'streaming' })
            break
          case 'correcting':
            updateLastAssistant(targetChatId, { sql: event.sql, status: 'streaming' })
            break
          case 'rows':
            updateLastAssistant(targetChatId, { rows: event.rows, rowCount: event.row_count, status: 'streaming' })
            break
          case 'chart':
            updateLastAssistant(targetChatId, { chart: event.chart })
            break
          case 'explanation_delta':
            updateLastAssistant(targetChatId, (m) => ({ explanation: m.explanation + event.text, status: 'streaming' }))
            break
          case 'followups':
            updateLastAssistant(targetChatId, { followups: event.questions })
            break
          case 'error':
            updateLastAssistant(targetChatId, { error: event.error, status: 'error' })
            break
          case 'done':
            updateLastAssistant(targetChatId, { status: 'done' })
            break
        }
      })
    } catch {
      updateLastAssistant(targetChatId, { error: 'Network error — is the backend running?', status: 'error' })
    } finally {
      setSending(false)
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(input)
    }
  }

  function handleNewChat() {
    setActiveChatId(null)
    setInput('')
  }

  function handleDeleteChat(id: string) {
    setChats((prev) => prev.filter((c) => c.id !== id))
    if (activeChatId === id) setActiveChatId(null)
  }

  function closeOnboarding() {
    setShowOnboarding(false)
    setSeenOnboarding()
  }

  function handleSelectDataset(id: string) {
    setActiveDatasetId(id)
    setActiveChatId(null) // switching datasets mid-chat would silently keep querying the old one — clearer to start fresh
  }

  async function handleUpload(file: File) {
    const ds = await uploadDataset(file)
    setDatasets((prev) => [...prev, ds])
    setActiveDatasetId(ds.dataset_id)
    setActiveChatId(null)
  }

  const messages = activeChat?.messages ?? []
  const isDefaultDataset = activeDatasetId === 'default'

  return (
    <div className="app-shell">
      {showOnboarding && <OnboardingTour onClose={closeOnboarding} />}

      <Sidebar
        chats={chats}
        datasets={datasets}
        activeChatId={activeChatId}
        onSelect={setActiveChatId}
        onNew={handleNewChat}
        onDelete={handleDeleteChat}
        theme={theme}
        onThemeChange={setTheme}
        onShowHelp={() => setShowOnboarding(true)}
      />

      <main className="main-col">
        <DatasetBar
          datasets={datasets}
          activeDatasetId={activeDatasetId}
          onSelect={handleSelectDataset}
          onUpload={handleUpload}
        />

        {messages.length === 0 ? (
          <div className="welcome">
            <div className="welcome-title">QueryMind</div>
            <p className="welcome-sub">Ask a question in plain English and get an answer, the exact SQL, and a chart when one fits.</p>
            <div className="dataset-banner">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <ellipse cx="12" cy="5" rx="8" ry="3" />
                <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
              </svg>
              Currently querying <strong>{selectedDataset.name}</strong> ({selectedDataset.row_count.toLocaleString()} rows)
            </div>

            {isDefaultDataset ? (
              <div className="example-categories">
                {EXAMPLE_CATEGORIES.map((cat) => (
                  <div key={cat.label}>
                    <div className="example-category-label">{cat.label}</div>
                    <div className="example-category-grid">
                      {cat.questions.map((ex) => (
                        <button key={ex} className="example-card" onClick={() => submit(ex)}>
                          {ex}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="example-categories">
                <div className="example-category-label">Try asking</div>
                <div className="example-category-grid">
                  {selectedDataset.example_questions.map((ex) => (
                    <button key={ex} className="example-card" onClick={() => submit(ex)}>
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="msg-scroll" ref={scrollRef}>
            <div className="msg-list">
              {messages.map((m) =>
                m.role === 'user' ? (
                  <UserBubble key={m.id} message={m} />
                ) : (
                  <AssistantBubble key={m.id} message={m} onFollowup={submit} />
                ),
              )}
            </div>
          </div>
        )}

        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask a question about the data..."
            rows={1}
            autoFocus
          />
          <button className="send-btn" onClick={() => submit(input)} disabled={sending || !input.trim()}>
            {sending ? (
              <span className="spinner" />
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            )}
          </button>
        </div>
      </main>
    </div>
  )
}
