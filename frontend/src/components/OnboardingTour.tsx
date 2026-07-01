import { useState } from 'react'

interface Step {
  icon: JSX.Element
  title: string
  body: string
}

const STEPS: Step[] = [
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
      </svg>
    ),
    title: 'Ask like you would ask a colleague',
    body: 'Type a plain-English question — no SQL needed. QueryMind translates it, runs it against the data, and explains the result in words.',
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" />
      </svg>
    ),
    title: "Nothing is a black box",
    body: 'Every answer shows the exact SQL that produced it — expand "Show SQL" any time to verify it yourself instead of taking the answer on faith.',
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M3 3v18h18M7 16l4-6 3 3 5-8" />
      </svg>
    ),
    title: 'Charts and follow-ups, automatically',
    body: 'When a result fits a chart, one appears on its own. Tap a suggested follow-up chip under the answer to keep digging without retyping the context.',
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
      </svg>
    ),
    title: 'What data is this actually asking?',
    body: 'Right now QueryMind is wired to one real dataset: 1M+ UK e-commerce transactions from 2009–2011 — revenue, products, customers, and countries. Every question is answered against that data, so ask about those angles.',
  },
]

export default function OnboardingTour({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0)
  const isLast = step === STEPS.length - 1
  const current = STEPS[step]

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
        <p className="onboarding-body">{current.body}</p>

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
