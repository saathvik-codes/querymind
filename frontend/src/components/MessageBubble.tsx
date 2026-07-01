import { useState } from 'react'
import type { AssistantMessage, UserMessage } from '../types'
import ResultChart from './ResultChart'
import StatCards from './StatCards'

export function UserBubble({ message }: { message: UserMessage }) {
  return (
    <div className="msg-row msg-row-user">
      <div className="msg-bubble msg-bubble-user">{message.text}</div>
    </div>
  )
}

export function AssistantBubble({
  message,
  onFollowup,
}: {
  message: AssistantMessage
  onFollowup: (question: string) => void
}) {
  const [showSql, setShowSql] = useState(false)
  const isStat = message.chart?.type === 'stat'
  const cols = message.rows && message.rows.length > 0 ? Object.keys(message.rows[0]) : []
  const showTable = message.rows && message.rows.length > 0 && !isStat

  return (
    <div className="msg-row msg-row-assistant">
      <div className="assistant-avatar">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2l2.4 7.2H22l-6 4.4 2.3 7.2L12 16.4 5.7 20.8 8 13.6 2 9.2h7.6z" />
        </svg>
      </div>
      <div className="msg-bubble msg-bubble-assistant">
        {message.status === 'pending' && (
          <div className="thinking">
            <span className="thinking-dot" />
            <span className="thinking-dot" />
            <span className="thinking-dot" />
          </div>
        )}

        {message.error && <div className="msg-error">{message.error}</div>}

        {message.sql && (
          <div className="sql-section">
            <button className="sql-toggle" onClick={() => setShowSql((s) => !s)}>
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                style={{ transform: showSql ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }}
              >
                <path d="M9 6l6 6-6 6" />
              </svg>
              {showSql ? 'Hide SQL' : 'Show SQL'}
              {message.cached && <span className="cached-badge">cached</span>}
            </button>
            {showSql && <pre className="sql-block">{message.sql}</pre>}
          </div>
        )}

        {showTable && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {cols.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {message.rows!.slice(0, 50).map((row, i) => (
                  <tr key={i}>
                    {cols.map((c) => (
                      <td key={c}>
                        {typeof row[c] === 'number'
                          ? Number(row[c]).toLocaleString(undefined, { maximumFractionDigits: 2 })
                          : String(row[c] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {message.rowCount !== undefined && message.rowCount > 50 && (
              <div className="row-count">{message.rowCount} rows total, showing first 50</div>
            )}
          </div>
        )}

        {isStat && message.chart?.type === 'stat' && message.rows && message.rows[0] && (
          <StatCards fields={message.chart.fields} row={message.rows[0]} />
        )}

        {!isStat && message.chart && message.chart.type !== 'stat' && message.rows && (
          <ResultChart chart={message.chart} rows={message.rows} />
        )}

        {message.explanation && (
          <p className="explanation">
            {message.explanation}
            {message.status === 'streaming' && <span className="cursor" />}
          </p>
        )}

        {message.status === 'done' && message.followups && message.followups.length > 0 && (
          <div className="followups">
            {message.followups.map((q) => (
              <button key={q} className="followup-chip" onClick={() => onFollowup(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
