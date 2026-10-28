export type ThemePreference = 'light' | 'dark' | 'system'

export const THEME_KEY = 'aia-theme'

export function storedTheme(): ThemePreference {
  const value = localStorage.getItem(THEME_KEY)
  return value === 'light' || value === 'dark' || value === 'system' ? value : 'system'
}

export function applyTheme(preference: ThemePreference) {
  const dark = preference === 'dark' || (preference === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

export function saveTheme(preference: ThemePreference) {
  localStorage.setItem(THEME_KEY, preference)
  applyTheme(preference)
}
