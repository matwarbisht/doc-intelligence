import { applyTheme, getThemePreference, saveThemePreference } from './theme';

describe('theme utility', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('defaults to the system preference', () => {
    expect(getThemePreference()).toBe('system');
  });

  it('persists and applies an explicit dark preference', () => {
    saveThemePreference('dark');

    expect(getThemePreference()).toBe('dark');
    expect(document.documentElement).toHaveClass('dark');
  });

  it('removes dark mode for an explicit light preference', () => {
    applyTheme('dark');
    saveThemePreference('light');

    expect(document.documentElement).not.toHaveClass('dark');
  });
});
