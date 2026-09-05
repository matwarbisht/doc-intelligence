import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';

import { App } from './App';

function renderApp(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}

describe('App', () => {
  it('renders the product foundation', () => {
    renderApp(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('heading', {
        name: /turn documents into intelligence/i,
      }),
    ).toBeVisible();
  });

  it('exposes the design-system playground', () => {
    renderApp(
      <MemoryRouter initialEntries={['/style-guide']}>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('heading', { name: /warm, restrained foundations/i }),
    ).toBeVisible();
    expect(
      screen.getByRole('group', { name: /theme preference/i }),
    ).toBeVisible();
  });
});
