'use client';

/**
 * src/app/page.js — Root route.
 *
 * Checks localStorage for a JWT:
 *   - Found  → redirect to /dashboard
 *   - Missing → redirect to /login
 *
 * Must be a Client Component because it accesses localStorage.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isLoggedIn } from '@/lib/auth';

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    if (isLoggedIn()) {
      router.replace('/dashboard');
    } else {
      router.replace('/login');
    }
  }, [router]);

  return null; // nothing to render — redirect happens immediately
}
