'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useAuthGuard, useLogout } from '@/lib/hooks';
import * as api from '@/lib/api';
import styles from './expense.module.css';

export default function ExpensePage() {
  const router = useRouter();
  const { id } = useParams(); // expenseId
  const searchParams = useSearchParams();
  const groupId = searchParams.get('groupId');
  const { token, user } = useAuthGuard();
  const logout = useLogout();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [expense, setExpense] = useState(null);
  const [group, setGroup] = useState(null);
  const [messages, setMessages] = useState([]);
  
  const [newMessage, setNewMessage] = useState('');
  const [posting, setPosting] = useState(false);
  
  const messagesEndRef = useRef(null);
  const esRef = useRef(null);

  useEffect(() => {
    if (!token) return;
    if (!groupId) {
      setError('Missing groupId parameter.');
      setLoading(false);
      return;
    }
    loadData();
  }, [token, id, groupId]);

  useEffect(() => {
    if (!token || !id) return;
    
    // Open Server-Sent Events stream for real-time messages
    const es = api.openMessageStream(token, id, (msg) => {
      setMessages((prev) => {
        // Prevent duplicates if we already fetched this message initially
        if (prev.some((m) => m.id === msg.id)) return prev;
        return [...prev, msg];
      });
    });
    esRef.current = es;
    
    return () => {
      if (esRef.current) {
        esRef.current.close();
      }
    };
  }, [token, id]);

  useEffect(() => {
    // Auto-scroll to bottom of chat
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const [grp, exp, msgs] = await Promise.all([
        api.getGroup(token, groupId),
        api.getExpense(token, groupId, id),
        api.getMessages(token, id),
      ]);
      setGroup(grp);
      setExpense(exp);
      setMessages(msgs);
    } catch (err) {
      if (err.message.includes('401') || err.message.includes('403')) {
        logout();
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSendMessage(e) {
    e.preventDefault();
    if (!newMessage.trim()) return;
    setPosting(true);
    try {
      await api.postMessage(token, id, newMessage.trim());
      setNewMessage('');
    } catch (err) {
      alert(err.message);
    } finally {
      setPosting(false);
    }
  }

  function getUserName(userId) {
    if (!group) return `User ${userId}`;
    const m = group.members.find((mem) => mem.user_id === userId);
    return m ? m.name : `User ${userId}`;
  }

  if (!token) return null;

  if (loading) return (
    <div className={styles.page}>
      <button className={styles.backBtn} onClick={() => router.push(`/groups/${groupId}`)}>← Back to Group</button>
      <p>Loading expense…</p>
    </div>
  );

  if (error) return (
    <div className={styles.page}>
      <button className={styles.backBtn} onClick={() => router.push(`/groups/${groupId}`)}>← Back to Group</button>
      <p className={styles.error}>{error}</p>
    </div>
  );

  if (!expense) return null;

  return (
    <div className={styles.page}>
      <button className={styles.backBtn} onClick={() => router.push(`/groups/${groupId}`)}>
        ← Back to Group
      </button>

      <div className={styles.container}>
        {/* LEFT COLUMN: Expense Details */}
        <div className={styles.leftCol}>
          <div className={styles.card}>
            <div className={styles.expHeader}>
              <h1 className={styles.title}>{expense.description}</h1>
              <p className={styles.amount}>${Number(expense.amount).toFixed(2)}</p>
            </div>
            
            <p className={styles.meta}>
              Paid by <strong>{getUserName(expense.paid_by)}</strong> on {new Date(expense.created_at).toLocaleDateString()}
            </p>
            <p className={styles.meta}>
              Split type: <strong>{expense.split_type}</strong>
            </p>

            <h3 className={styles.splitsTitle}>Splits</h3>
            <ul className={styles.splitList}>
              {expense.splits?.map((split, i) => (
                <li key={i} className={styles.splitItem}>
                  <span className={styles.splitName}>{getUserName(split.user_id)}</span>
                  <span className={styles.splitAmount}>
                    ${Number(split.amount_owed).toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* RIGHT COLUMN: Chat */}
        <div className={styles.rightCol}>
          <div className={styles.chatCard}>
            <h2 className={styles.chatTitle}>Expense Chat</h2>
            
            <div className={styles.messagesArea}>
              {messages.length === 0 ? (
                <p className={styles.emptyChat}>No messages yet.</p>
              ) : (
                messages.map((m) => {
                  const isMe = m.user_id === user?.id;
                  return (
                    <div key={m.id} className={`${styles.msgBubbleWrapper} ${isMe ? styles.mine : styles.theirs}`}>
                      {!isMe && <span className={styles.msgName}>{getUserName(m.user_id)}</span>}
                      <div className={`${styles.msgBubble} ${isMe ? styles.mineBubble : styles.theirsBubble}`}>
                        {m.content}
                      </div>
                      <span className={styles.msgTime}>
                        {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            <form className={styles.chatForm} onSubmit={handleSendMessage}>
              <input
                className={styles.chatInput}
                type="text"
                placeholder="Type a message…"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                maxLength={500}
                required
              />
              <button type="submit" className={styles.chatSendBtn} disabled={posting || !newMessage.trim()}>
                {posting ? '...' : 'Send'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
