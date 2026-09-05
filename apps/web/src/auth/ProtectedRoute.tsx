import { Navigate, Outlet, useLocation } from 'react-router';

import { useAuth } from './useAuth';

export function ProtectedRoute() {
  const { loading, user } = useAuth();
  const location = useLocation();

  if (loading) return <p>Restoring your session…</p>;
  if (!user) {
    return <Navigate to="/sign-in" replace state={{ from: location }} />;
  }
  return <Outlet />;
}
