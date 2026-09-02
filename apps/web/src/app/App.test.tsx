import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { App } from './App';

describe('App', () => {
  it('renders the product foundation', () => {
    render(
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
    render(
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
