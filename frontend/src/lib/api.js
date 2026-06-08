/**
 * src/lib/api.js
 *
 * Single source of truth for every API call.
 * All functions return the parsed JSON body on success,
 * and throw an Error with the server's detail message on failure.
 *
 * Usage:
 *   import * as api from '@/lib/api';
 *   const data = await api.login('alice@test.com', 'pass123');
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// ── Internal helper ────────────────────────────────────────────────────────────

async function request(method, path, body = null, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // 204 No Content — return null
  if (res.status === 204) return null;

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data?.detail ?? `Request failed: ${res.status}`);
  }
  return data;
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export async function register(name, email, password) {
  return request('POST', '/auth/register', { name, email, password });
}

export async function login(email, password) {
  return request('POST', '/auth/login', { email, password });
}

// ── Groups ─────────────────────────────────────────────────────────────────────

export async function getGroups(token) {
  return request('GET', '/groups', null, token);
}

export async function getGroup(token, id) {
  return request('GET', `/groups/${id}`, null, token);
}

export async function createGroup(token, name) {
  return request('POST', '/groups', { name }, token);
}

export async function renameGroup(token, id, name) {
  return request('PATCH', `/groups/${id}`, { name }, token);
}

export async function addMember(token, groupId, email) {
  return request('POST', `/groups/${groupId}/members`, { email }, token);
}

export async function removeMember(token, groupId, userId) {
  return request('DELETE', `/groups/${groupId}/members/${userId}`, null, token);
}

// ── Expenses ───────────────────────────────────────────────────────────────────

export async function getExpenses(token, groupId) {
  return request('GET', `/groups/${groupId}/expenses`, null, token);
}

export async function getExpense(token, groupId, expenseId) {
  return request('GET', `/groups/${groupId}/expenses/${expenseId}`, null, token);
}

export async function getUserExpenses(token) {
  return request('GET', '/users/me/expenses', null, token);
}

export async function addExpense(token, groupId, payload) {
  return request('POST', `/groups/${groupId}/expenses`, payload, token);
}

export async function editExpense(token, groupId, expenseId, payload) {
  return request('PUT', `/groups/${groupId}/expenses/${expenseId}`, payload, token);
}

export async function deleteExpense(token, groupId, expenseId) {
  return request('DELETE', `/groups/${groupId}/expenses/${expenseId}`, null, token);
}

// ── Balances ───────────────────────────────────────────────────────────────────

export async function getGroupBalances(token, groupId) {
  return request('GET', `/groups/${groupId}/balances`, null, token);
}

export async function getSimplifiedBalances(token, groupId) {
  return request('GET', `/groups/${groupId}/balances/simplified`, null, token);
}

export async function getUserSummary(token) {
  return request('GET', '/users/me/summary', null, token);
}

// ── Payments ───────────────────────────────────────────────────────────────────

export async function recordPayment(token, groupId, payload) {
  return request('POST', `/groups/${groupId}/payments`, payload, token);
}

export async function getPayments(token, groupId) {
  return request('GET', `/groups/${groupId}/payments`, null, token);
}

// ── Messages ───────────────────────────────────────────────────────────────────

export async function getMessages(token, expenseId) {
  return request('GET', `/expenses/${expenseId}/messages`, null, token);
}

export async function postMessage(token, expenseId, content) {
  return request('POST', `/expenses/${expenseId}/messages`, { content }, token);
}

/**
 * Opens an SSE stream for real-time expense chat.
 * Returns an EventSource. Caller is responsible for closing it.
 *
 * Note: EventSource doesn't support custom headers natively.
 * We pass the token as a query param and the backend reads it from there.
 * For now, SSE auth uses a simple workaround: token in query string.
 *
 * Usage:
 *   const es = openMessageStream(token, expenseId, (msg) => { ... });
 *   // later:
 *   es.close();
 */
export function openMessageStream(token, expenseId, onMessage) {
  const url = `${BASE}/expenses/${expenseId}/messages/stream?token=${encodeURIComponent(token)}`;
  const es = new EventSource(url);
  es.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data));
    } catch (_) {}
  };
  return es;
}
