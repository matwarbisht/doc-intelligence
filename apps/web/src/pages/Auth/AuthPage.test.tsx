import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';

import { api } from '../../api/client';
import { AuthContext } from '../../auth/context';
import { AuthPage } from './AuthPage';

vi.mock('../../api/client', () => ({
  api: { getCapabilities: vi.fn() },
}));

afterEach(() => {
  vi.clearAllMocks();
});

it('disables public registration when the server closes sign-up', async () => {
  vi.mocked(api.getCapabilities).mockResolvedValue({
    public_signup: false,
    uploads: true,
    processing: true,
    processing_retries: true,
    ask: true,
  });
  const signUp = vi.fn();

  render(
    <AuthContext.Provider
      value={{
        session: null,
        user: null,
        loading: false,
        configurationError: null,
        signUp,
        signIn: vi.fn(),
        signOut: vi.fn(),
      }}
    >
      <MemoryRouter>
        <AuthPage mode="sign-up" />
      </MemoryRouter>
    </AuthContext.Provider>,
  );

  expect(
    await screen.findByText(/registration is temporarily unavailable/i),
  ).toBeVisible();
  const submit = screen.getByRole('button', { name: 'Create account' });
  expect(submit).toBeDisabled();
  fireEvent.click(submit);
  expect(signUp).not.toHaveBeenCalled();
});
