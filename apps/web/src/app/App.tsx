import { useQueryClient } from '@tanstack/react-query';
import { Link, NavLink, Route, Routes } from 'react-router';

import { ProtectedRoute } from '../auth/ProtectedRoute';
import { useAuth } from '../auth/useAuth';
import { HomePage } from '../pages/HomePage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { DocumentsPage } from '../pages/Documents/DocumentsPage';
import { DocumentDetailPage } from '../pages/Documents/DocumentDetailPage';
import { QueryPage } from '../pages/Query/QueryPage';
import { StyleGuide } from '../pages/StyleGuide/StyleGuide';
import { AuthPage } from '../pages/Auth/AuthPage';
import styles from './App.module.scss';

export function App() {
  const { signOut, user } = useAuth();
  const queryClient = useQueryClient();

  async function handleSignOut() {
    await signOut();
    queryClient.clear();
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          Document Intelligence
        </Link>
        <nav className={styles.navigation} aria-label="Primary navigation">
          <NavLink className={styles.navLink} to="/" end>
            Home
          </NavLink>
          {user ? (
            <>
              <NavLink className={styles.navLink} to="/documents">
                Documents
              </NavLink>
              <NavLink className={styles.navLink} to="/ask">
                Ask
              </NavLink>
            </>
          ) : null}
          <NavLink className={styles.navLink} to="/style-guide">
            Style guide
          </NavLink>
          {user ? (
            <button
              className={styles.accountAction}
              onClick={() => void handleSignOut()}
            >
              Sign out
            </button>
          ) : (
            <NavLink className={styles.navLink} to="/sign-in">
              Sign in
            </NavLink>
          )}
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/sign-in" element={<AuthPage mode="sign-in" />} />
          <Route path="/sign-up" element={<AuthPage mode="sign-up" />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/ask" element={<QueryPage />} />
            <Route
              path="/documents/:documentId"
              element={<DocumentDetailPage />}
            />
          </Route>
          <Route path="/style-guide" element={<StyleGuide />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}
