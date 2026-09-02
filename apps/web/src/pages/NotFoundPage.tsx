import { Link } from 'react-router';
import styles from './NotFoundPage.module.scss';

export function NotFoundPage() {
  return (
    <section className={styles.page}>
      <div>
        <p>404</p>
        <h1>Page not found.</h1>
        <Link to="/">Return home</Link>
      </div>
    </section>
  );
}
