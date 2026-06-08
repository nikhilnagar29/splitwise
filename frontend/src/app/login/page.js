'use client';

/**
 * src/app/login/page.js — Screen 1: Login + Register
 *
 * Two modes on the same page, toggled by a tab:
 *   - Login:    email + password
 *   - Register: name + email + password
 *
 * On success:
 *   - Saves JWT + user info to localStorage via auth.js helpers.
 *   - Redirects to /dashboard.
 *
 * On error:
 *   - Shows the server's detail message under the form.
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';
import { saveAuth, isLoggedIn } from '@/lib/auth';
import styles from './login.module.css';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode]       = useState('login');   // 'login' | 'register'
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  // Form fields
  const [name, setName]         = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');

  // If already logged in, skip straight to dashboard
  useEffect(() => {
    if (isLoggedIn()) router.replace('/dashboard');
  }, [router]);

  function resetForm() {
    setName('');
    setEmail('');
    setPassword('');
    setError('');
  }

  function switchMode(next) {
    setMode(next);
    resetForm();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let data;
      if (mode === 'login') {
        data = await api.login(email, password);
      } else {
        data = await api.register(name, email, password);
      }

      // data = { access_token, token_type, user_id, name, email }
      saveAuth(data.access_token, {
        id:    data.user_id,
        name:  data.name,
        email: data.email,
      });

      router.push('/dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>

        {/* ── Header ── */}
        <h1 className={styles.title}>Splitwise Clone</h1>
        <p className={styles.subtitle}>
          {mode === 'login'
            ? 'Sign in to see your groups and balances.'
            : 'Create an account to get started.'}
        </p>

        {/* ── Mode tabs ── */}
        <div className={styles.tabs}>
          <button
            type="button"
            className={`${styles.tab} ${mode === 'login' ? styles.active : ''}`}
            onClick={() => switchMode('login')}
          >
            Login
          </button>
          <button
            type="button"
            className={`${styles.tab} ${mode === 'register' ? styles.active : ''}`}
            onClick={() => switchMode('register')}
          >
            Register
          </button>
        </div>

        {/* ── Form ── */}
        <form className={styles.form} onSubmit={handleSubmit}>

          {mode === 'register' && (
            <div className={styles.field}>
              <label htmlFor="name">Full name</label>
              <input
                id="name"
                type="text"
                placeholder="Alice"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoComplete="name"
              />
            </div>
          )}

          <div className={styles.field}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              placeholder="alice@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <button
            id="submit-btn"
            type="submit"
            className={styles.submitBtn}
            disabled={loading}
          >
            {loading
              ? (mode === 'login' ? 'Signing in…' : 'Creating account…')
              : (mode === 'login' ? 'Sign in' : 'Create account')}
          </button>
        </form>

        {/* ── Switch prompt ── */}
        <p className={styles.switchText}>
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            type="button"
            className={styles.switchLink}
            onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
          >
            {mode === 'login' ? 'Register' : 'Sign in'}
          </button>
        </p>

      </div>
    </div>
  );
}
