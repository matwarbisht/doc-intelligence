import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@radix-ui/colors/olive.css';
import '@radix-ui/colors/olive-dark.css';
import '@radix-ui/colors/amber.css';
import '@radix-ui/colors/amber-dark.css';
import '@radix-ui/colors/red.css';
import '@radix-ui/colors/red-dark.css';
import '@radix-ui/colors/green.css';
import '@radix-ui/colors/green-dark.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';

import { App } from './app/App';
import { AppProviders } from './app/providers';
import './styles/globals.scss';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </StrictMode>,
);
