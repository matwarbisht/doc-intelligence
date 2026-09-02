import type { ButtonHTMLAttributes } from 'react';

import styles from './Button.module.scss';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({
  className,
  type = 'button',
  variant = 'primary',
  ...props
}: ButtonProps) {
  const classes = [styles.button, styles[variant], className]
    .filter(Boolean)
    .join(' ');

  return (
    <button className={classes} data-variant={variant} type={type} {...props} />
  );
}
