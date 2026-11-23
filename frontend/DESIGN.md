# QueryMind design notes

The idea: **an analyst's notebook.** The product answers questions with a table, a chart and a sentence, so the page
is set like a printed report: paper background, hairline rules, numbers that line up, and one colour.

## What this replaced

The first version was the stock "AI chat" look: near-black background, Inter and Space Grotesk, an indigo gradient
wordmark with a sparkle logo, glowing background blob, and five accent-colour dots in the sidebar. It could have been
any product.

## References

Taken as direction only (the sources are design blogs, not the companies themselves):

- Linear and Vercel: a single neutral sans for the interface, a monospace for code and figures, very little chrome.
- Datawrapper and the data-journalism desks it cites: sans for labels, monospace or tabular figures for numbers,
  serif for prose, so charts read like part of an article.

## Choices

| Part | Now | Why |
|---|---|---|
| Interface text | IBM Plex Sans | Neutral, built for dense UI, free |
| SQL and numbers | IBM Plex Mono, tabular figures | Digits line up in tables and chart axes |
| Answers and the page title | Source Serif 4 | The answer is prose; a serif reads like a report, not a chat bubble |
| Colour | Warm paper `#f5f2ea`, ink `#1f1c16`, ledger green `#1f5f4a` | One accent, used for actions and chart bars |
| Shapes | 4 to 8 px radius, hairline borders, no shadows | Flat and printed, not floating cards |
| Logo | A plain magnifier drawn in ink with a green handle | No gradient, no sparkle |
| Theme control | Light and dark only | Five colour dots were decoration, not function |

Charts use compact axis labels (1.6M) so long numbers are never clipped.
