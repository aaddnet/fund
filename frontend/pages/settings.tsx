import { useState } from 'react';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import {
  AuthUser,
  listAuthUsers,
  createAuthUser,
  updateAuthUser,
  resetAuthUserPassword,
  unlockAuthUser,
  changeMyPassword,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  users: AuthUser[];
  error?: string;
};

const ROLES = ['admin', 'ops', 'ops-readonly', 'support', 'client-readonly'];

export default function Page({ users: initialUsers, error }: Props) {
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canManage = hasPermission('auth.manage');

  // User management state
  const [users, setUsers] = useState<AuthUser[]>(initialUsers);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AuthUser | null>(null);
  const [resetTarget, setResetTarget] = useState<AuthUser | null>(null);

  // Create/edit form
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('ops');
  const [isActive, setIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Reset password form
  const [newPasswordReset, setNewPasswordReset] = useState('');

  // Change own password form
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [changingPw, setChangingPw] = useState(false);

  function openCreate() {
    setUsername('');
    setPassword('');
    setDisplayName('');
    setRole('ops');
    setIsActive(true);
    setIsCreateOpen(true);
  }

  function openEdit(user: AuthUser) {
    setDisplayName(user.display_name || '');
    setRole(user.role);
    setIsActive(user.is_active);
    setEditingUser(user);
  }

  function openReset(user: AuthUser) {
    setNewPasswordReset('');
    setResetTarget(user);
  }

  function closeModals() {
    setIsCreateOpen(false);
    setEditingUser(null);
    setResetTarget(null);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canManage) return;
    setSubmitting(true);
    try {
      const user = await createAuthUser({ username, password, role, display_name: displayName || null, is_active: isActive });
      setUsers((prev) => [...prev, user]);
      showToast(t('userCreated'), 'success');
      closeModals();
    } catch (err) {
      showToast(err instanceof Error ? err.message : t('userCreated'), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!canManage || !editingUser) return;
    setSubmitting(true);
    try {
      const updated = await updateAuthUser(editingUser.id, { role, display_name: displayName || null, is_active: isActive });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      showToast(t('userUpdated'), 'success');
      closeModals();
    } catch (err) {
      showToast(err instanceof Error ? err.message : t('userUpdated'), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!canManage || !resetTarget) return;
    setSubmitting(true);
    try {
      await resetAuthUserPassword(resetTarget.id, newPasswordReset);
      showToast(t('passwordReset'), 'success');
      closeModals();
    } catch (err) {
      showToast(err instanceof Error ? err.message : t('passwordReset'), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUnlock(user: AuthUser) {
    if (!canManage) return;
    try {
      await unlockAuthUser(user.id);
      setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, locked_until: null, failed_login_attempts: 0 } : u)));
      showToast(t('userUnlocked'), 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : t('userUnlocked'), 'error');
    }
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setChangingPw(true);
    try {
      await changeMyPassword({ current_password: currentPw, new_password: newPw });
      showToast(t('passwordChanged'), 'success');
      setCurrentPw('');
      setNewPw('');
    } catch (err) {
      showToast(err instanceof Error ? err.message : t('passwordChanged'), 'error');
    } finally {
      setChangingPw(false);
    }
  }

  return (
    <Layout title={t('settings')} subtitle='User management and account settings' requiredPermission='nav.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      {canManage && (
        <div style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0 }}>{t('userManagement')}</h3>
            <button style={styles.buttonPrimary} onClick={openCreate}>+ {t('createUser')}</button>
          </div>
          <ProductTable
            emptyText='No users found.'
            rows={users}
            columns={[
              { key: 'id', title: 'ID', render: (u) => `#${u.id}` },
              { key: 'username', title: 'Username', render: (u) => <strong>{u.username}</strong> },
              { key: 'display_name', title: 'Display Name', render: (u) => u.display_name || '—' },
              { key: 'role', title: t('role'), render: (u) => u.role },
              {
                key: 'active',
                title: t('active'),
                render: (u) => (
                  <span style={{ color: u.is_active ? colors.success : colors.danger }}>
                    {u.is_active ? t('yes') : t('no')}
                  </span>
                ),
              },
              {
                key: 'locked',
                title: t('locked'),
                render: (u) => u.locked_until ? (
                  <span style={{ color: colors.danger }}>
                    {new Date(u.locked_until) > new Date() ? 'Locked' : '—'}
                  </span>
                ) : '—',
              },
              { key: 'last_login', title: 'Last Login', render: (u) => u.last_login_at ? u.last_login_at.slice(0, 10) : '—' },
              {
                key: 'actions',
                title: t('actions'),
                render: (u: AuthUser) => (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button style={{ ...styles.buttonSecondary, padding: '3px 8px', fontSize: 12 }} onClick={() => openEdit(u)}>
                      {t('editUser')}
                    </button>
                    <button style={{ ...styles.buttonSecondary, padding: '3px 8px', fontSize: 12 }} onClick={() => openReset(u)}>
                      {t('resetPassword')}
                    </button>
                    {u.locked_until && new Date(u.locked_until) > new Date() && (
                      <button style={{ ...styles.buttonSecondary, padding: '3px 8px', fontSize: 12 }} onClick={() => handleUnlock(u)}>
                        {t('unlock')}
                      </button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}

      <div style={{ ...styles.card, marginTop: 20, maxWidth: 440 }}>
        <h3 style={{ marginTop: 0 }}>{t('changePassword')}</h3>
        <form onSubmit={handleChangePassword} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('currentPassword')}>
            <input
              required
              type='password'
              style={styles.input}
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              disabled={changingPw}
              autoComplete='current-password'
            />
          </FormField>
          <FormField label={t('newPassword')}>
            <input
              required
              type='password'
              style={styles.input}
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              disabled={changingPw}
              autoComplete='new-password'
              minLength={8}
            />
          </FormField>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button style={styles.buttonPrimary} type='submit' disabled={changingPw}>
              {changingPw ? t('submitting') : t('savePassword')}
            </button>
          </div>
        </form>
      </div>

      {/* Create User Modal */}
      <Modal isOpen={isCreateOpen} onClose={closeModals} title={t('createUser')}>
        <form onSubmit={handleCreate} style={{ display: 'grid', gap: 14 }}>
          <FormField label='Username'>
            <input required style={styles.input} value={username} onChange={(e) => setUsername(e.target.value)} disabled={submitting} autoComplete='off' />
          </FormField>
          <FormField label='Display Name'>
            <input style={styles.input} value={displayName} onChange={(e) => setDisplayName(e.target.value)} disabled={submitting} />
          </FormField>
          <FormField label={t('password')}>
            <input required type='password' style={styles.input} value={password} onChange={(e) => setPassword(e.target.value)} disabled={submitting} minLength={8} autoComplete='new-password' />
          </FormField>
          <FormField label={t('role')}>
            <select style={styles.input} value={role} onChange={(e) => setRole(e.target.value)} disabled={submitting}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </FormField>
          <FormField label={t('active')}>
            <select style={styles.input} value={isActive ? 'true' : 'false'} onChange={(e) => setIsActive(e.target.value === 'true')} disabled={submitting}>
              <option value='true'>{t('yes')}</option>
              <option value='false'>{t('no')}</option>
            </select>
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type='button' onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>{t('reset')}</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('submitting') : t('createUser')}
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit User Modal */}
      <Modal isOpen={!!editingUser} onClose={closeModals} title={`${t('editUser')}: ${editingUser?.username}`}>
        <form onSubmit={handleEdit} style={{ display: 'grid', gap: 14 }}>
          <FormField label='Display Name'>
            <input style={styles.input} value={displayName} onChange={(e) => setDisplayName(e.target.value)} disabled={submitting} />
          </FormField>
          <FormField label={t('role')}>
            <select style={styles.input} value={role} onChange={(e) => setRole(e.target.value)} disabled={submitting}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </FormField>
          <FormField label={t('active')}>
            <select style={styles.input} value={isActive ? 'true' : 'false'} onChange={(e) => setIsActive(e.target.value === 'true')} disabled={submitting}>
              <option value='true'>{t('yes')}</option>
              <option value='false'>{t('no')}</option>
            </select>
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type='button' onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>{t('reset')}</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('submitting') : 'Save Changes'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal isOpen={!!resetTarget} onClose={closeModals} title={`${t('resetPassword')}: ${resetTarget?.username}`}>
        <form onSubmit={handleResetPassword} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('newPassword')}>
            <input
              required
              type='password'
              style={styles.input}
              value={newPasswordReset}
              onChange={(e) => setNewPasswordReset(e.target.value)}
              disabled={submitting}
              minLength={8}
              autoComplete='new-password'
            />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type='button' onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>{t('reset')}</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('submitting') : t('resetPassword')}
            </button>
          </div>
        </form>
      </Modal>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  const permissions: string[] = auth.initialUser?.permissions ?? [];
  const canManage = permissions.includes('auth.manage');

  if (!canManage) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        users: [],
      },
    };
  }

  try {
    const users = await listAuthUsers(auth.accessToken);
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        users: users ?? [],
      },
    };
  } catch (error) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        users: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
