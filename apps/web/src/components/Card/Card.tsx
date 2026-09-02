import type { HTMLAttributes } from 'react';

import styles from './Card.module.scss';

export type CardProps = HTMLAttributes<HTMLDivElement>;

export function Card({ className, ...props }: CardProps) {
  const classes = [styles.card, className].filter(Boolean).join(' ');

  return <div className={classes} {...props} />;
}
