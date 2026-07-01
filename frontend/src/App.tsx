import { useState, KeyboardEvent } from 'react'

const API = '/api'

const EXAMPLES = [
  'Which country generated the most revenue?',
  'Top 5 products by total revenue?',
  'How many unique customers each month in 2011?',
  'Average order value by country?',
  'Which month had the highest revenue?',
  'Products with more than 10,000 total units sold?',
]

interface Row { [key: string]: unknown }

interface Result {
  question: string
  sql: string
  rows: Row[]
  answer: string | null
  error: string | null
}

function ResultCard({ result }: { result: Result }) {
  const [showSql, setShowSql] = useState(false)
  const cols = result.rows.length > 0 ? Object.keys(result.rows[0]) : []

  if (result.error) {
    return (
      <div className="error-card">
        <strong>Error:</strong> {result.error}
        <pre style={{ marginTop: 8, fontSize: 11, whiteSpace: 'pre-wrap' }}>{result.sql}</pre>
      </div>
    )
  }

  return (
    <div className="result-card">
      <div className="result-header">
        <div className="question">{result.question}</div>
        {result.answer && <div className="answer">{result.answer}</div>}
      </div>
      <div className="sql-toggle" onClick={() => setShowSql(s => !s)}>
        {showSql ? '▲' : '▼'} {showSql ? 'Hide SQL' : 'Show SQL'}
      </div>
      {showSql && <div className="sql-block">{result.sql}</div>}
      {result.rows.length > 0 && (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>{cols.map(c => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {result.rows.slice(0, 50).map((row, i) => (
                  <tr key={i}>
                    {cols.map(c => (
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
          </div>
          <div className="row-count">
            {result.rows.length} row{result.rows.length !== 1 ? 's' : ''} returned
            {result.rows.length > 50 && ` · showing first 50`}
          </div>
        </>
      )}
    </div>
  )
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<Result[]>([])

  const submit = async (q: string) => {
    const text = q.trim()
    if (!text || loading) return
    setLoading(true)
    setQuestion('')
    try {
      const res = await fetch(`${API}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
      })
      const data: Result = await res.json()
      setHistory(h => [data, ...h])
    } catch {
      setHistory(h => [{ question: text, sql: '', rows: [], answer: null, error: 'Network error — is the backend running?' }, ...h])
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') submit(question)
  }

  return (
    <div className="wrap">
      <div className="header">
        <h1>QueryMind <span className="badge">LIVE</span></h1>
        <p>Ask anything about 1M+ UK e-commerce transactions (2009–2011) · powered by LangChain + DuckDB</p>
      </div>

      <div className="chips">
        {EXAMPLES.map(ex => (
          <div className="chip" key={ex} onClick={() => submit(ex)}>{ex}</div>
        ))}
      </div>

      <div className="input-row">
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask a question about the data..."
          autoFocus
        />
        <button onClick={() => submit(question)} disabled={loading || !question.trim()}>
          {loading ? <span className="spinner" /> : 'Ask'}
        </button>
      </div>

      {history.map((r, i) => <ResultCard key={i} result={r} />)}

      {history.length === 0 && (
        <div style={{ textAlign: 'center', color: '#94a3b8', padding: '60px 0', fontSize: 14 }}>
          Click a question above or type your own to get started.
        </div>
      )}
    </div>
  )
}
