import type { Chat, ThemeState } from '../types'

const CHATS_KEY = 'querymind.chats.v1'
const THEME_KEY = 'querymind.theme.v1'

export function loadChats(): Chat[] {
  try {
    const raw = localStorage.getItem(CHATS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveChats(chats: Chat[]): void {
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats))
  } catch {
    // storage full or unavailable (private browsing) — chat history just won't persist
  }
}

const DEFAULT_THEME: ThemeState = { palette: 'indigo', mode: 'dark' }

export function loadTheme(): ThemeState {
  try {
    const raw = localStorage.getItem(THEME_KEY)
    if (!raw) return DEFAULT_THEME
    return { ...DEFAULT_THEME, ...JSON.parse(raw) }
  } catch {
    return DEFAULT_THEME
  }
}

export function saveTheme(theme: ThemeState): void {
  try {
    localStorage.setItem(THEME_KEY, JSON.stringify(theme))
  } catch {
    // ignore
  }
}

const ONBOARDED_KEY = 'querymind.onboarded.v1'

export function hasSeenOnboarding(): boolean {
  try {
    return localStorage.getItem(ONBOARDED_KEY) === 'true'
  } catch {
    return false
  }
}

export function setSeenOnboarding(): void {
  try {
    localStorage.setItem(ONBOARDED_KEY, 'true')
  } catch {
    // ignore
  }
}
