import { useQuery } from '@tanstack/react-query';

import { api } from './client';

export const capabilitiesQueryKey = ['capabilities'] as const;

export function useCapabilities() {
  return useQuery({
    queryKey: capabilitiesQueryKey,
    queryFn: ({ signal }) => api.getCapabilities({ signal }),
    staleTime: 30_000,
  });
}
