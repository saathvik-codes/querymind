# QueryMind — Natural Language Analytics Interface

**Live demo:** https://querymind-saathvik.vercel.app

Ask plain-English questions about a real e-commerce dataset. QueryMind translates
them to DuckDB SQL using a LangChain NL2SQL chain, executes the query, and returns
a natural-language answer alongside the exact SQL for full transparency.

**Data**: UCI "Online Retail II" — 1,041,670 real UK transaction lines,
Dec 2009–Dec 2011, £17.87M in revenue, 5,878 customers.

## What makes this different

Most NL2SQL demos either use tiny toy datasets or hide the SQL. QueryMind:

- Shows the generated SQL every time (collapsible in the UI), so the user can verify
  correctness — it doesn't ask you to trust the answer
- Self-corrects: if the generated SQL fails, the error and query are sent back to the
  LLM with instructions to fix it (up to 2 attempts)
- Is backed by a real, documented dataset with independently verifiable findings
- Supports two LLM backends (Claude via `ANTHROPIC_API_KEY`, or a local Ollama model)
  without code changes — just set the `LLM=ollama` env var
- Guards against the failure mode most NL2SQL demos ignore: the LLM-generated
  SQL runs against a connection that's shared across every request for the
  process's lifetime, so a hallucinated or injected `DROP TABLE` / `DELETE`
  wouldn't just fail one query — it would corrupt data for every other user
  until restart. `backend/schema.py::validate_readonly_sql` rejects anything
  that isn't a single `SELECT`/`WITH` statement (stacked `; DROP ...` included)
  before it ever reaches the database, independent of what the LLM was asked
  or tricked into generating

## Verified query coverage

All 12 analytical query types run and verified directly against DuckDB (without LLM):

| Query | Result |
|---|---|
| Country by revenue | United Kingdom: £17.87M |
| Top product by revenue | REGENCY CAKESTAND 3 TIER: £344,563 |
| Unique customers per month (Jan 2011) | 741 |
| Highest avg order value by country | Netherlands: £108.93 |
| Peak revenue month | November 2011: £1.51M |
| Customers with 10+ purchases | 876 |
| % orders outside UK | 7.98% |
| Revenue by year | 2009: £825K / 2010: £7.3M / 2011: £9.7M |
| Orders by day of week | Thursday peak (197,252 orders) |
| Avg qty per invoice | 285 units |

## Tech stack

- **LLM**: Claude (`claude-haiku-4-5`) or Ollama (`llama3.1:8b`) via LangChain
- **Query engine**: DuckDB (in-process, no database server needed)
- **Backend**: FastAPI, async NL→SQL→explain chain
- **Frontend**: React 18, TypeScript, Vite
- **Data**: UCI Online Retail II (public, citable)

## Running locally

```bash
# Backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key   # or set LLM=ollama + OLLAMA_MODEL
cd backend && uvicorn main:app --reload --port 8030

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# Open http://localhost:5200
```

## Running the eval

```bash
# Requires backend running
cd eval && python run_eval.py
```

## Project structure

```
backend/
  main.py       FastAPI app (/query, /schema, /examples, /health)
  chain.py      NL→SQL chain with self-correction (supports Claude + Ollama)
  schema.py     DuckDB connection + schema context for the LLM
data/
  retail.csv    UCI Online Retail II, pre-cleaned (gitignored — regenerate with scripts)
eval/
  eval_cases.json   12 test cases with verifiable expectations
  run_eval.py       End-to-end evaluator against the live API
frontend/
  src/App.tsx   Chat UI: question chips, input, result cards, SQL toggle, results table
```
