import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { HomePage } from './HomePage';

it('hides developer API documentation outside development', () => {
  render(
    <MemoryRouter>
      <HomePage showApiDocumentation={false} />
    </MemoryRouter>,
  );

  expect(
    screen.queryByRole('link', { name: /api documentation/i }),
  ).not.toBeInTheDocument();
});

it('shows API documentation during local development', () => {
  render(
    <MemoryRouter>
      <HomePage showApiDocumentation />
    </MemoryRouter>,
  );

  expect(
    screen.getByRole('link', { name: /api documentation/i }),
  ).toHaveAttribute('href', 'http://localhost:8000/docs');
});
