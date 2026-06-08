/**
 * src/lib/hooks.js
 *
 * Shared React hooks used across multiple pages.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { getToken, getUser, clearAuth } from '@/lib/auth';

/**
 * useAuthGuard()
 *
 * Returns { token, user } for authenticated pages.
 * If no token is found in localStorage, immediately redirects to /login.
 *
 * Usage:
 *   const { token, user } = useAuthGuard();
 *   if (!token) return null; // redirect in flight
 */
export function useAuthGuard() {
  const router = useRouter();
  const [auth, setAuth] = useState({ token: null, user: null });

  useEffect(() => {
    const token = getToken();
    const user  = getUser();
    if (!token) {
      router.replace('/login');
    } else {
      setAuth({ token, user });
    }
  }, [router]);

  return auth;
}

/**
 * useLogout()
 *
 * Returns a logout() function that clears auth state and
 * redirects to /login.
 */
export function useLogout() {
  const router = useRouter();
  return useCallback(function logout() {
    clearAuth();
    router.replace('/login');
  }, [router]);
}
