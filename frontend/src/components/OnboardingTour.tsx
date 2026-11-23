import { useState } from 'react'
import type { DatasetInfo } from '../types'

interface Step {
  icon: JSX.Element
  title: string
  // A function body is built from the dataset the user currently has selected
  body: string | ((dataset?: DatasetInfo) => string)
}

function describeDataset(d?: DatasetInfo): string {
  if (!d || d.row_count === 0) {
    return 'QueryMind answers questions about the dataset you have selected. Pick one from the bar at the top, or upload your own CSV.'
  }
  const cols = d.columns.slice(0, 6).map((c) => c.name).join(', ')
  return (
    `You are asking ${d.name}: ${d.row_count.toLocaleString()} rows` +
    (cols ? ` with columns such as ${cols}` : '') +
    '. Every question is answered against this data, so ask about those columns. ' +
    'You can switch datasets or upload your own CSV from the bar at the top.'
  )
}

const STEPS: Step[] = [
  {
    icon: <img src="/illustrations/qm-tour-ask.webp" alt="" width={200} height={150} className="illus" />,
    title: 'Ask like you would ask a colleague',
    body: 'Type a plain-English question — no SQL needed. QueryMind translates it, runs it against the data, and explains the result in words.',
  },
  {
    icon: <img src="/illustrations/qm-tour-sql.webp" alt="" width={200} height={150} className="illus" />,
    title: "Nothing is a black box",
    body: 'Every answer shows the exact SQL that produced it — expand "Show SQL" any time to verify it yourself instead of taking the answer on faith.',
  },
  {
    icon: <img src="/illustrations/qm-tour-chart.webp" alt="" width={200} height={150} className="illus" />,
    title: 'Charts and follow-ups, automatically',
    body: 'When a result fits a chart, one appears on its own. Tap a suggested follow-up chip under the answer to keep digging without retyping the context.',
  },
  {
    icon: <img src="/illustrations/qm-tour-share.webp" alt="" width={200} height={150} className="illus" />,
    title: 'What data is this actually asking?',
    body: describeDataset,
  },
]

export default function OnboardingTour({ onClose, dataset }: { onClose: () => void; dataset?: DatasetInfo }) {
  const [step, setStep] = useState(0)
  const isLast = step === STEPS.length - 1
  const current = STEPS[step]
  const body = typeof current.body === 'function' ? current.body(dataset) : current.body

  return (
    <div className="onboarding-backdrop" onClick={onClose}>
      <div className="onboarding-card" onClick={(e) => e.stopPropagation()}>
        <button className="onboarding-skip" onClick={onClose}>
          Skip
        </button>

        <div className="onboarding-icon" key={step}>
          {current.icon}
        </div>
        <h2 className="onboarding-title">{current.title}</h2>
        <p className="onboarding-body">{body}</p>

        <div className="onboarding-dots">
          {STEPS.map((_, i) => (
            <span key={i} className={`onboarding-dot ${i === step ? 'active' : ''}`} onClick={() => setStep(i)} />
          ))}
        </div>

        <div className="onboarding-actions">
          {step > 0 && (
            <button className="onboarding-btn-secondary" onClick={() => setStep((s) => s - 1)}>
              Back
            </button>
          )}
          <button
            className="onboarding-btn-primary"
            onClick={() => (isLast ? onClose() : setStep((s) => s + 1))}
          >
            {isLast ? 'Get started' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  )
}
