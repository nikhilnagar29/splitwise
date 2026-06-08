'use client';

/**
 * src/app/dashboard/page.js — Screen 2: Dashboard
 *
 * Shows:
 *   - Header: "My Groups" + logged-in user name + Logout button
 *   - List of all groups the user belongs to (name + member count)
 *   - "Create Group" button that toggles an inline text input + submit
 *   - Clicking a group navigates to /groups/[id]
 *
 * On load: GET /groups with JWT.
 * 401/403 from API → redirect to /login.
 * Logout → clear localStorage → redirect to /login.
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthGuard, useLogout } from '@/lib/hooks';
import * as api from '@/lib/api';
import styles from './dashboard.module.css';

export default function DashboardPage() {
  const router  = useRouter();
  const { token, user } = useAuthGuard();
  const logout  = useLogout();

  const [groups,    setGroups]    = useState([]);
  const [expenses,  setExpenses]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');

  // Create-group form state
  const [showForm,  setShowForm]  = useState(false);
  const [newName,   setNewName]   = useState('');
  const [creating,  setCreating]  = useState(false);
  const [createErr, setCreateErr] = useState('');

  // ── Fetch data ──────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const [groupsData, expensesData] = await Promise.all([
        api.getGroups(token),
        api.getUserExpenses(token)
      ]);
      setGroups(groupsData);
      setExpenses(expensesData);
    } catch (err) {
      // 401/403 → session expired
      if (err.message.includes('401') || err.message.includes('403') ||
          err.message.toLowerCase().includes('not authenticated')) {
        logout();
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [token, logout]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Create group ────────────────────────────────────────────
  async function handleCreate(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setCreateErr('');
    try {
      const group = await api.createGroup(token, newName.trim());
      setGroups((prev) => [group, ...prev]);
      setNewName('');
      setShowForm(false);
    } catch (err) {
      setCreateErr(err.message);
    } finally {
      setCreating(false);
    }
  }

  // Guard: wait until token is resolved
  if (!token) return null;

  return (
    <div className={styles.page}>

      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <h1>My Groups</h1>
          {user && <p>Signed in as <strong>{user.name}</strong></p>}
        </div>
        <button
          id="logout-btn"
          className={styles.logoutBtn}
          onClick={logout}
        >
          Logout
        </button>
      </header>

      {/* ── Create group ── */}
      <section className={styles.createSection}>
        {!showForm ? (
          <button
            id="create-group-btn"
            className={styles.createBtn}
            onClick={() => { setShowForm(true); setCreateErr(''); }}
          >
            + Create Group
          </button>
        ) : (
          <form className={styles.createForm} onSubmit={handleCreate}>
            <input
              id="new-group-name"
              className={styles.createInput}
              type="text"
              placeholder="Group name (e.g. Trip to Goa)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
              required
            />
            <button
              id="create-group-submit"
              type="submit"
              className={styles.createSubmit}
              disabled={creating}
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
            <button
              type="button"
              className={styles.cancelBtn}
              onClick={() => { setShowForm(false); setNewName(''); setCreateErr(''); }}
            >
              Cancel
            </button>
          </form>
        )}
        {createErr && <p className={styles.error} style={{ marginTop: '0.5rem' }}>{createErr}</p>}
      </section>

      {/* ── Group list ── */}
      <section style={{ marginBottom: '2rem' }}>
        <p className={styles.sectionTitle}>
          {groups.length > 0
            ? `${groups.length} group${groups.length !== 1 ? 's' : ''}`
            : 'Groups'}
        </p>

        {error && <p className={styles.error}>{error}</p>}

        {loading ? (
          <p>Loading…</p>
        ) : groups.length === 0 ? (
          <p className={styles.empty}>No groups yet. Create one above!</p>
        ) : (
          <ul className={styles.groupList} aria-label="Group list">
            {groups.map((g) => (
              <li key={g.id}>
                <button
                  id={`group-${g.id}`}
                  className={styles.groupCard}
                  onClick={() => router.push(`/groups/${g.id}`)}
                >
                  <div>
                    <p className={styles.groupName}>{g.name}</p>
                    <p className={styles.groupMeta}>
                      {g.members
                        ? `${g.members.length} member${g.members.length !== 1 ? 's' : ''}`
                        : 'View details →'}
                    </p>
                  </div>
                  <span className={styles.groupArrow}>›</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Recent Expenses ── */}
      <section>
        <p className={styles.sectionTitle}>Recent Expenses</p>
        
        {loading ? (
          <p>Loading…</p>
        ) : expenses.length === 0 ? (
          <p className={styles.empty}>You have no recent expenses.</p>
        ) : (
          <ul className={styles.groupList}>
            {expenses.map((exp) => {
              // Find group name for context
              const group = groups.find(g => g.id === exp.group_id);
              const groupName = group ? group.name : `Group ${exp.group_id}`;
              
              return (
                <li key={exp.id}>
                  <button
                    className={styles.groupCard}
                    onClick={() => router.push(`/expenses/${exp.id}?groupId=${exp.group_id}`)}
                  >
                    <div>
                      <p className={styles.groupName}>{exp.description}</p>
                      <p className={styles.groupMeta}>
                        In {groupName} · {exp.split_type} split
                      </p>
                    </div>
                    <span style={{ fontWeight: 600, fontSize: '1.1rem' }}>
                      ${Number(exp.amount).toFixed(2)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

    </div>
  );
}
