import {
  createDocumentApiClient,
  DEFAULT_API_BASE_URL,
} from '@doc-intelligence/api-client';

import { getAccessToken } from '../auth/supabase';

export const api = createDocumentApiClient(
  import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE_URL,
  getAccessToken,
);
