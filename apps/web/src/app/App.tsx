import { Link, NavLink, Route, Routes } from 'react-router';

import { HomePage } from '../pages/HomePage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { DocumentsPage } from '../pages/Documents/DocumentsPage';
import { StyleGuide } from '../pages/StyleGuide/StyleGuide';
import styles from './App.module.scss';

export function App() {
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
          <NavLink className={styles.navLink} to="/documents">
            Documents
          </NavLink>
          <NavLink className={styles.navLink} to="/style-guide">
            Style guide
          </NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/style-guide" element={<StyleGuide />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}
