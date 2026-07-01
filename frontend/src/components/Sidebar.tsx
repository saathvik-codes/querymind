import type { Chat, DatasetInfo, ThemeState } from '../types'
import ThemeSwitcher from './ThemeSwitcher'
import LogoMark from './LogoMark'

function timeAgo(ts: number): string {
  const diffMin = Math.max(0, Math.round((Date.now() - ts) / 60000))
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return `${Math.round(diffHr / 24)}d ago`
}

export default function Sidebar({
  chats,
  datasets,
  activeChatId,
  onSelect,
  onNew,
  onDelete,
  theme,
  onThemeChange,
  onShowHelp,
}: {
  chats: Chat[]
  datasets: DatasetInfo[]
  activeChatId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  theme: ThemeState
  onThemeChange: (theme: ThemeState) => void
  onShowHelp: () => void
}) {
  const sorted = [...chats].sort((a, b) => b.createdAt - a.createdAt)
  const datasetName = (id: string) => datasets.find((d) => d.dataset_id === id)?.name

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <LogoMark size={26} />
          <span className="brand-name">QueryMind</span>
        </div>
        <button className="new-chat-btn" onClick={onNew}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New chat
        </button>
      </div>

      <div className="chat-list">
        {sorted.length === 0 && <div className="chat-list-empty">No saved chats yet</div>}
        {sorted.map((chat) => (
          <div
            key={chat.id}
            className={`chat-list-item ${chat.id === activeChatId ? 'active' : ''}`}
            onClick={() => onSelect(chat.id)}
          >
            <div className="chat-list-item-text">
              <div className="chat-list-title">{chat.title || 'New chat'}</div>
              <div className="chat-list-time">
                {timeAgo(chat.createdAt)}
                {chat.datasetId !== 'default' && (
                  <span className="chat-dataset-tag"> · {datasetName(chat.datasetId) ?? 'custom dataset'}</span>
                )}
              </div>
            </div>
            <button
              className="chat-delete-btn"
              title="Delete chat"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(chat.id)
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <button className="help-link" onClick={onShowHelp}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 2-3 4M12 17h.01" />
          </svg>
          How it works
        </button>
        <ThemeSwitcher theme={theme} onChange={onThemeChange} />
      </div>
    </aside>
  )
}
