/**
 * src/lib/auth.js
 *
 * Token storage helpers. Centralise all localStorage access here
 * so nothing else touches it directly.
 */

const KEY = 'sw_token';
const USER_KEY = 'sw_user';

export function saveAuth(token, user) {
  localStorage.setItem(KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getToken() {
  return localStorage.getItem(KEY);
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
}

export function clearAuth() {
  localStorage.removeItem(KEY);
  localStorage.removeItem(USER_KEY);
}

export function isLoggedIn() {
  return Boolean(getToken());
}
