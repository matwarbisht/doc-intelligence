import { useEffect, useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router';

import { useAuth } from '../../auth/useAuth';
import { Button } from '../../components/Button/Button';
import { Card } from '../../components/Card/Card';
import { Input } from '../../components/Input/Input';
import styles from './AuthPage.module.scss';

interface AuthPageProps {
  mode: 'sign-in' | 'sign-up';
}

interface ReturnLocationState {
  from?: { pathname?: string; search?: string };
}

export function AuthPage({ mode }: AuthPageProps) {
  const { configurationError, loading, signIn, signUp, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const returnState = location.state as ReturnLocationState | null;
  const destination = `${returnState?.from?.pathname ?? '/documents'}${returnState?.from?.search ?? ''}`;

  useEffect(() => {
    if (user) navigate(destination, { replace: true });
  }, [destination, navigate, user]);

  if (!loading && user) return <Navigate to={destination} replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === 'sign-up') await signUp(email.trim(), password);
      else await signIn(email.trim(), password);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Authentication failed.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  const signingUp = mode === 'sign-up';
  return (
    <section className={styles.page}>
      <div className={styles.introduction}>
        <p className={styles.eyebrow}>Private document intelligence</p>
        <h1>{signingUp ? 'Create your account.' : 'Welcome back.'}</h1>
        <p>
          Your documents, extracted knowledge, and questions are isolated to
          your account.
        </p>
      </div>
      <Card className={styles.card}>
        <form onSubmit={submit}>
          <label htmlFor="auth-email">Email address</label>
          <Input
            id="auth-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <label htmlFor="auth-password">Password</label>
          <Input
            id="auth-password"
            type="password"
            autoComplete={signingUp ? 'new-password' : 'current-password'}
            minLength={8}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {configurationError ? (
            <p className={styles.error} role="alert">
              {configurationError}
            </p>
          ) : null}
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          <Button
            type="submit"
            disabled={submitting || Boolean(configurationError)}
          >
            {submitting
              ? signingUp
                ? 'Creating account…'
                : 'Signing in…'
              : signingUp
                ? 'Create account'
                : 'Sign in'}
          </Button>
        </form>
        <p className={styles.alternative}>
          {signingUp
            ? 'Already have an account?'
            : 'New to Document Intelligence?'}{' '}
          <Link to={signingUp ? '/sign-in' : '/sign-up'}>
            {signingUp ? 'Sign in' : 'Create an account'}
          </Link>
        </p>
      </Card>
    </section>
  );
}
