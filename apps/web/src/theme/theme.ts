export type ThemePreference = 'light' | 'dark' | 'system';

const storageKey = 'doc-intelligence-theme';
const systemDarkQuery = '(prefers-color-scheme: dark)';

function isThemePreference(value: string | null): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system';
}

export function getThemePreference(): ThemePreference {
  const storedPreference = window.localStorage.getItem(storageKey);
  return isThemePreference(storedPreference) ? storedPreference : 'system';
}

export function applyTheme(preference: ThemePreference): void {
  const isDark =
    preference === 'dark' ||
    (preference === 'system' && window.matchMedia(systemDarkQuery).matches);

  document.documentElement.classList.toggle('dark', isDark);
  document.documentElement.dataset.theme = preference;
}

export function saveThemePreference(preference: ThemePreference): void {
  window.localStorage.setItem(storageKey, preference);
  applyTheme(preference);
}

export function subscribeToSystemTheme(onChange: () => void): () => void {
  const mediaQuery = window.matchMedia(systemDarkQuery);
  mediaQuery.addEventListener('change', onChange);
  return () => mediaQuery.removeEventListener('change', onChange);
}
