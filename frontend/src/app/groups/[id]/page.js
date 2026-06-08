'use client';

/**
 * src/app/groups/[id]/page.js — Screen 3: Group Detail
 *
 * Section 1 — Group Header
 *   Group name, member list (name + role badge).
 *   Admin sees: Add Member input + Remove button on each non-admin member.
 *
 * Section 2 — Expenses
 *   List of expenses (description, amount, paid-by name, split type).
 *   "Add Expense" toggles an inline form.
 *   Clicking an expense navigates to /expenses/[id].
 *
 * Section 3 — Balances (Simplified)
 *   "X owes Y — $amount" rows.
 *   "Settle Up" button per row calls POST /groups/{id}/payments and reloads.
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuthGuard, useLogout } from '@/lib/hooks';
import { getUser } from '@/lib/auth';
import * as api from '@/lib/api';
import styles from './group.module.css';

// ── helpers ──────────────────────────────────────────────────────────────────

function buildUserMap(members) {
  // Returns { [user_id]: { name, email, role } }
  const map = {};
  for (const m of members) map[m.user_id] = m;
  return map;
}

function userName(userMap, id) {
  return userMap[id]?.name ?? `User ${id}`;
}

// ── component ─────────────────────────────────────────────────────────────────

export default function GroupDetailPage() {
  const { id: groupId } = useParams();
  const router          = useRouter();
  const { token }       = useAuthGuard();
  const logout          = useLogout();
  const currentUser     = getUser();

  // ── data state ──────────────────────────────────────────────────────────────
  const [group,    setGroup]    = useState(null);
  const [expenses, setExpenses] = useState([]);
  const [balances, setBalances] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');

  // derived
  const members = group?.members ?? [];
  const userMap = buildUserMap(members);
  const isAdmin = members.some(
    (m) => m.user_id === currentUser?.id && m.role === 'admin'
  );

  // ── Add-member form ─────────────────────────────────────────────────────────
  const [memberEmail,  setMemberEmail]  = useState('');
  const [memberLoading, setMemberLoading] = useState(false);
  const [memberError,  setMemberError]  = useState('');

  // ── Add-expense form ────────────────────────────────────────────────────────
  const [showExpForm,   setShowExpForm]   = useState(false);
  const [expDesc,       setExpDesc]       = useState('');
  const [expAmount,     setExpAmount]     = useState('');
  const [expPaidBy,     setExpPaidBy]     = useState('');
  const [expSplitType,  setExpSplitType]  = useState('equal');
  const [expUserIds,    setExpUserIds]    = useState(new Set());
  const [expValues,     setExpValues]     = useState({});  // { userId: string }
  const [expLoading,    setExpLoading]    = useState(false);
  const [expError,      setExpError]      = useState('');

  // ── Settle state ────────────────────────────────────────────────────────────
  const [settlingId,   setSettlingId]    = useState(null); // "payerId-receiverId"

  // ── Loaders ─────────────────────────────────────────────────────────────────

  const loadBalances = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api.getSimplifiedBalances(token, groupId);
      setBalances(data.transactions ?? []);
    } catch (_) {}
  }, [token, groupId]);

  const loadAll = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const [grp, exps, bals] = await Promise.all([
        api.getGroup(token, groupId),
        api.getExpenses(token, groupId),
        api.getSimplifiedBalances(token, groupId),
      ]);
      setGroup(grp);
      setExpenses(exps);
      setBalances(bals.transactions ?? []);

      // Default paid-by to current user if they're a member
      if (grp.members?.some((m) => m.user_id === currentUser?.id)) {
        setExpPaidBy(String(currentUser?.id));
      } else if (grp.members?.length > 0) {
        setExpPaidBy(String(grp.members[0].user_id));
      }
    } catch (err) {
      if (err.message.includes('401') || err.message.includes('403')) {
        logout();
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [token, groupId, logout, currentUser?.id]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ── Add member ──────────────────────────────────────────────────────────────

  async function handleAddMember(e) {
    e.preventDefault();
    if (!memberEmail.trim()) return;
    setMemberLoading(true);
    setMemberError('');
    try {
      await api.addMember(token, groupId, memberEmail.trim());
      setMemberEmail('');
      await loadAll(); // refresh members
    } catch (err) {
      setMemberError(err.message);
    } finally {
      setMemberLoading(false);
    }
  }

  async function handleRemoveMember(userId) {
    if (!confirm(`Remove this member from the group?`)) return;
    try {
      await api.removeMember(token, groupId, userId);
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  // ── Add expense ─────────────────────────────────────────────────────────────

  function toggleExpUser(userId) {
    setExpUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
        setExpValues((v) => { const nv = { ...v }; delete nv[userId]; return nv; });
      } else {
        next.add(userId);
      }
      return next;
    });
  }

  function resetExpForm() {
    setExpDesc('');
    setExpAmount('');
    setExpSplitType('equal');
    setExpUserIds(new Set());
    setExpValues({});
    setExpError('');
  }

  async function handleAddExpense(e) {
    e.preventDefault();
    setExpError('');

    const userIds = Array.from(expUserIds);
    if (userIds.length === 0) {
      setExpError('Select at least one member to split with.');
      return;
    }

    let values = [];
    if (expSplitType === 'exact' || expSplitType === 'percentage') {
      values = userIds.map((uid) => parseFloat(expValues[uid] ?? 0));
      if (values.some(isNaN)) {
        setExpError('Fill in all split values.');
        return;
      }
    }

    setExpLoading(true);
    try {
      await api.addExpense(token, groupId, {
        description: expDesc.trim(),
        amount:      parseFloat(expAmount),
        paid_by:     parseInt(expPaidBy),
        split_type:  expSplitType,
        user_ids:    userIds,
        values,
      });
      resetExpForm();
      setShowExpForm(false);
      // Reload both expenses and balances
      const [exps] = await Promise.all([
        api.getExpenses(token, groupId),
        loadBalances(),
      ]);
      setExpenses(exps);
    } catch (err) {
      setExpError(err.message);
    } finally {
      setExpLoading(false);
    }
  }

  // ── Settle up ───────────────────────────────────────────────────────────────

  async function handleSettle(payerId, receiverId, amount) {
    const key = `${payerId}-${receiverId}`;
    setSettlingId(key);
    try {
      await api.recordPayment(token, groupId, {
        from_user_id: payerId,
        to_user_id:   receiverId,
        amount,
      });
      await loadBalances();
    } catch (err) {
      setError(err.message);
    } finally {
      setSettlingId(null);
    }
  }

  // ── Guards ──────────────────────────────────────────────────────────────────

  if (!token) return null;

  if (loading) return (
    <div className={styles.page}>
      <button className={styles.backBtn} onClick={() => router.push('/dashboard')}>← Back to Dashboard</button>
      <p>Loading group…</p>
    </div>
  );

  if (error) return (
    <div className={styles.page}>
      <button className={styles.backBtn} onClick={() => router.push('/dashboard')}>← Back to Dashboard</button>
      <p className={styles.error}>{error}</p>
    </div>
  );

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className={styles.page}>

      {/* ── Back ── */}
      <button className={styles.backBtn} onClick={() => router.push('/dashboard')}>
        ← Back to Dashboard
      </button>

      {/* ════════════════════════════════════════════════════════════
          SECTION 1 — Group Header + Members
          ════════════════════════════════════════════════════════════ */}
      <h1 className={styles.groupName}>{group?.name}</h1>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Members ({members.length})</h2>

        <ul className={styles.memberList}>
          {members.map((m) => (
            <li key={m.user_id}>
              <div className={styles.memberRow}>
                <span className={styles.memberName}>{m.name}</span>
                <span className={`${styles.memberRole} ${m.role === 'admin' ? styles.admin : ''}`}>
                  {m.role}
                </span>
                {isAdmin && m.role !== 'admin' && (
                  <button
                    className={styles.removeBtn}
                    onClick={() => handleRemoveMember(m.user_id)}
                  >
                    Remove
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>

        {/* Add member — admin only */}
        {isAdmin && (
          <>
            <form className={styles.addMemberForm} onSubmit={handleAddMember}>
              <input
                className={styles.inlineInput}
                type="email"
                placeholder="Add member by email…"
                value={memberEmail}
                onChange={(e) => setMemberEmail(e.target.value)}
                required
              />
              <button type="submit" className={styles.primaryBtn} disabled={memberLoading}>
                {memberLoading ? 'Adding…' : 'Add Member'}
              </button>
            </form>
            {memberError && <p className={styles.error}>{memberError}</p>}
          </>
        )}
      </section>

      {/* ════════════════════════════════════════════════════════════
          SECTION 2 — Expenses
          ════════════════════════════════════════════════════════════ */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Expenses ({expenses.length})</h2>

        {/* Expense list */}
        {expenses.length === 0 ? (
          <p className={styles.empty}>No expenses yet.</p>
        ) : (
          <ul className={styles.expenseList}>
            {expenses.map((exp) => (
              <li key={exp.id}>
                <button
                  className={styles.expenseCard}
                  onClick={() => router.push(`/expenses/${exp.id}?groupId=${groupId}`)}
                >
                  <div>
                    <p className={styles.expDesc}>{exp.description}</p>
                    <p className={styles.expMeta}>
                      Paid by {userName(userMap, exp.paid_by)} · {exp.split_type} split
                    </p>
                  </div>
                  <span className={styles.expAmount}>${Number(exp.amount).toFixed(2)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* Add expense toggle */}
        {!showExpForm ? (
          <button
            className={styles.primaryBtn}
            style={{ marginTop: '0.75rem' }}
            onClick={() => { resetExpForm(); setShowExpForm(true); }}
          >
            + Add Expense
          </button>
        ) : (
          <form className={styles.addExpenseForm} onSubmit={handleAddExpense}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>New Expense</h3>

            {/* Description */}
            <div className={styles.formRow}>
              <label>Description</label>
              <input
                type="text"
                placeholder="e.g. Dinner at restaurant"
                value={expDesc}
                onChange={(e) => setExpDesc(e.target.value)}
                required
              />
            </div>

            {/* Amount */}
            <div className={styles.formRow}>
              <label>Total Amount ($)</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                placeholder="0.00"
                value={expAmount}
                onChange={(e) => setExpAmount(e.target.value)}
                required
              />
            </div>

            {/* Paid by */}
            <div className={styles.formRow}>
              <label>Paid by</label>
              <select value={expPaidBy} onChange={(e) => setExpPaidBy(e.target.value)} required>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>{m.name}</option>
                ))}
              </select>
            </div>

            {/* Split type */}
            <div className={styles.formRow}>
              <label>Split type</label>
              <select
                value={expSplitType}
                onChange={(e) => {
                  setExpSplitType(e.target.value);
                  setExpValues({});
                }}
              >
                <option value="equal">Equal</option>
                <option value="exact">Exact amounts</option>
                <option value="percentage">Percentage</option>
              </select>
            </div>

            {/* Who's included */}
            <div className={styles.formRow}>
              <label>Split between</label>
              <div className={styles.checkboxGrid}>
                {members.map((m) => (
                  <label key={m.user_id} className={styles.checkboxItem}>
                    <input
                      type="checkbox"
                      checked={expUserIds.has(m.user_id)}
                      onChange={() => toggleExpUser(m.user_id)}
                    />
                    {m.name}
                  </label>
                ))}
              </div>
            </div>

            {/* Per-user values (exact / percentage only) */}
            {expSplitType !== 'equal' && expUserIds.size > 0 && (
              <div className={styles.formRow}>
                <label>
                  {expSplitType === 'exact' ? 'Amount for each person ($)' : 'Percentage for each person (%)'}
                </label>
                <div className={styles.valuesGrid}>
                  {Array.from(expUserIds).map((uid) => (
                    <div key={uid} className={styles.valueRow}>
                      <span>{userName(userMap, uid)}</span>
                      <input
                        className={styles.valueInput}
                        type="number"
                        min="0"
                        step={expSplitType === 'exact' ? '0.01' : '1'}
                        placeholder={expSplitType === 'exact' ? '0.00' : '0'}
                        value={expValues[uid] ?? ''}
                        onChange={(e) =>
                          setExpValues((prev) => ({ ...prev, [uid]: e.target.value }))
                        }
                      />
                      <span>{expSplitType === 'percentage' ? '%' : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {expError && <p className={styles.error}>{expError}</p>}

            <div className={styles.formActions}>
              <button type="submit" className={styles.primaryBtn} disabled={expLoading}>
                {expLoading ? 'Saving…' : 'Save Expense'}
              </button>
              <button
                type="button"
                className={styles.secondaryBtn}
                onClick={() => { setShowExpForm(false); resetExpForm(); }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </section>

      {/* ════════════════════════════════════════════════════════════
          SECTION 3 — Simplified Balances
          ════════════════════════════════════════════════════════════ */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Balances</h2>

        {balances.length === 0 ? (
          <p className={styles.empty}>All settled up! 🎉</p>
        ) : (
          <ul className={styles.balanceList}>
            {balances.map((b) => {
              const key      = `${b.payer_id}-${b.receiver_id}`;
              const settling = settlingId === key;
              return (
                <li key={key}>
                  <div className={styles.balanceRow}>
                    <p className={styles.balanceText}>
                      <span className={styles.balanceName}>{userName(userMap, b.payer_id)}</span>
                      {' owes '}
                      <span className={styles.balanceName}>{userName(userMap, b.receiver_id)}</span>
                      {' — '}
                      <span className={styles.balanceAmt}>${Number(b.amount).toFixed(2)}</span>
                    </p>
                    <button
                      className={styles.settleBtn}
                      disabled={settling}
                      onClick={() => handleSettle(b.payer_id, b.receiver_id, b.amount)}
                    >
                      {settling ? 'Settling…' : 'Settle Up'}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

    </div>
  );
}
