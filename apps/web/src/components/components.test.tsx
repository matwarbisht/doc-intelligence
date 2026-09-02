import { render, screen } from '@testing-library/react';

import { Button } from './Button/Button';
import { Card } from './Card/Card';
import { Input } from './Input/Input';

describe('design-system components', () => {
  it('passes native props through Button', () => {
    render(<Button disabled>Process document</Button>);

    expect(
      screen.getByRole('button', { name: 'Process document' }),
    ).toBeDisabled();
  });

  it('associates Input with a native label', () => {
    render(
      <label>
        Document name
        <Input placeholder="Annual report" />
      </label>,
    );

    expect(screen.getByLabelText('Document name')).toHaveAttribute(
      'placeholder',
      'Annual report',
    );
  });

  it('renders Card content', () => {
    render(<Card>Source evidence</Card>);

    expect(screen.getByText('Source evidence')).toBeVisible();
  });
});
