import type { Session, User } from '@supabase/supabase-js';
import { createContext } from 'react';

import { authConfigurationError } from './supabase';

export interface AuthContextValue {
  session: Session | null;
  user: User | null;
  loading: boolean;
  configurationError: string | null;
  signUp(email: string, password: string): Promise<void>;
  signIn(email: string, password: string): Promise<void>;
  signOut(): Promise<void>;
}

const unavailable = async () => {
  throw new Error(authConfigurationError ?? 'Authentication is unavailable.');
};

export const AuthContext = createContext<AuthContextValue>({
  session: null,
  user: null,
  loading: false,
  configurationError: authConfigurationError,
  signUp: unavailable,
  signIn: unavailable,
  signOut: unavailable,
});

export { unavailable };
