import type { InputHTMLAttributes } from 'react';

import styles from './Input.module.scss';

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: InputProps) {
  const classes = [styles.input, className].filter(Boolean).join(' ');

  return <input className={classes} {...props} />;
}
