import { useState } from 'react';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import {
  AuthUser,
  ExchangeRate,
  AssetPrice,
  listAuthUsers,
  createAuthUser,
  updateAuthUser,
  resetAuthUserPassword,
  unlockAuthUser,
  changeMyPassword,
  getRates,
  upsertRateManual,
  fetchRateFromApi,
  importRatesCsv,
  getPrices,
  upsertPriceManual,
  importPricesCsv,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type SettingsTab = 'users' | 'rates' | 'prices';

type Props = {
  users: AuthUser[];
  rates: ExchangeRate[];
  prices: AssetPrice[];
  error?: string;
};

const ROLES = ['admin', 'ops', 'ops-readonly', 'support', 'client-readonly'];

export default function Page({ users: initialUsers, rates: initialRates, prices: initialPrices, error }: Props) {
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canManage = hasPermission('auth.manage');
  const [activeTab, setActiveTab] = useState<SettingsTab>('users');

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

  // Exchange rate state
  const [rates, setRates] = useState<ExchangeRate[]>(initialRates);
  const [rateBase, setRateBase] = useState('HKD');
  const [rateQuote, setRateQuote] = useState('USD');
  const [rateValue, setRateValue] = useState('');
  const [rateDate, setRateDate] = useState('');
  const [rateSubmitting, setRateSubmitting] = useState(false);

  // Asset price state
  const [prices, setPrices] = useState<AssetPrice[]>(initialPrices);
  const [priceAsset, setPriceAsset] = useState('');
  const [priceUsd, setPriceUsd] = useState('');
  const [priceDate, setPriceDate] = useState('');
  const [priceSubmitting, setPriceSubmitting] = useState(false);

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

  async function handleAddRate(e: React.FormEvent) {
    e.preventDefault();
    setRateSubmitting(true);
    try {
      const row = await upsertRateManual({ base: rateBase.toUpperCase(), quote: rateQuote.toUpperCase(), rate: parseFloat(rateValue), snapshot_date: rateDate });
      setRates((prev) => [row, ...prev.filter((r) => !(r.base_currency === row.base_currency && r.quote_currency === row.quote_currency && r.snapshot_date === row.snapshot_date))]);
      showToast('汇率已保存', 'success');
      setRateValue('');
    } catch (err) {
      showToast(err instanceof Error ? err.message : '保存失败', 'error');
    } finally {
      setRateSubmitting(false);
    }
  }

  async function handleFetchRate(e: React.FormEvent) {
    e.preventDefault();
    setRateSubmitting(true);
    try {
      const row = await fetchRateFromApi({ base: rateBase.toUpperCase(), quote: rateQuote.toUpperCase(), snapshot_date: rateDate });
      setRates((prev) => [row, ...prev.filter((r) => !(r.base_currency === row.base_currency && r.quote_currency === row.quote_currency && r.snapshot_date === row.snapshot_date))]);
      showToast(`已获取: ${row.rate}`, 'success');
      setRateValue(String(row.rate));
    } catch (err) {
      showToast(err instanceof Error ? err.message : '获取失败', 'error');
    } finally {
      setRateSubmitting(false);
    }
  }

  async function handleRateCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await importRatesCsv(file);
      showToast(`已导入 ${res.imported} 条汇率`, 'success');
      const refreshed = await getRates({ size: 100 });
      setRates(refreshed.items ?? []);
    } catch (err) {
      showToast(err instanceof Error ? err.message : '导入失败', 'error');
    }
    e.target.value = '';
  }

  async function handleAddPrice(e: React.FormEvent) {
    e.preventDefault();
    setPriceSubmitting(true);
    try {
      const row = await upsertPriceManual({ asset_code: priceAsset.toUpperCase(), price_usd: parseFloat(priceUsd), snapshot_date: priceDate });
      setPrices((prev) => [row, ...prev.filter((p) => !(p.asset_code === row.asset_code && p.snapshot_date === row.snapshot_date))]);
      showToast('价格已保存', 'success');
      setPriceUsd('');
    } catch (err) {
      showToast(err instanceof Error ? err.message : '保存失败', 'error');
    } finally {
      setPriceSubmitting(false);
    }
  }

  async function handlePriceCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await importPricesCsv(file);
      showToast(`已导入 ${res.imported} 条价格`, 'success');
      const refreshed = await getPrices({ size: 100 });
      setPrices(refreshed.items ?? []);
    } catch (err) {
      showToast(err instanceof Error ? err.message : '导入失败', 'error');
    }
    e.target.value = '';
  }

  const tabStyle = (key: SettingsTab) => ({
    padding: '10px 18px', border: 'none', background: 'transparent', cursor: 'pointer',
    fontWeight: activeTab === key ? 700 : 400,
    color: activeTab === key ? colors.primary : colors.muted,
    borderBottom: activeTab === key ? `2px solid ${colors.primary}` : '2px solid transparent',
    marginBottom: -2, fontSize: 14,
  });

  return (
    <Layout title={t('settings')} subtitle='User management, exchange rates and asset prices' requiredPermission='nav.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: `2px solid ${colors.border}` }}>
        <button style={tabStyle('users')} onClick={() => setActiveTab('users')}>用户管理</button>
        <button style={tabStyle('rates')} onClick={() => setActiveTab('rates')}>汇率管理</button>
        <button style={tabStyle('prices')} onClick={() => setActiveTab('prices')}>资产价格</button>
      </div>

      {activeTab === 'users' && (
        <>
        {canManage && <div style={styles.card}>
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
        </div>}

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
      </>)}

      {/* Exchange Rate Tab */}
      {activeTab === 'rates' && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>汇率管理</h3>
          <form onSubmit={handleAddRate} style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 16, alignItems: 'flex-end' }}>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>基础币种</div>
              <input style={{ ...styles.input, width: 80 }} value={rateBase} onChange={(e) => setRateBase(e.target.value.toUpperCase())} placeholder='HKD' required />
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>目标币种</div>
              <input style={{ ...styles.input, width: 80 }} value={rateQuote} onChange={(e) => setRateQuote(e.target.value.toUpperCase())} placeholder='USD' required />
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>日期</div>
              <input type='date' style={styles.input} value={rateDate} onChange={(e) => setRateDate(e.target.value)} required />
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>汇率</div>
              <input style={{ ...styles.input, width: 120 }} type='number' step='0.000001' value={rateValue} onChange={(e) => setRateValue(e.target.value)} placeholder='0.128' />
            </div>
            <button style={styles.buttonPrimary} type='submit' disabled={rateSubmitting || !rateValue}>手动录入</button>
            <button style={styles.buttonSecondary} type='button' disabled={rateSubmitting || !rateDate} onClick={handleFetchRate}>从 Frankfurter 拉取</button>
            <label style={{ ...styles.buttonSecondary, cursor: 'pointer' }}>
              批量 CSV
              <input type='file' accept='.csv' style={{ display: 'none' }} onChange={handleRateCsv} />
            </label>
          </form>
          <div style={{ fontSize: 12, color: colors.muted, marginBottom: 8 }}>CSV 格式: date,from_currency,to_currency,rate</div>
          <ProductTable
            emptyText='暂无汇率记录'
            rows={rates}
            columns={[
              { key: 'date', title: '日期', render: (r) => r.snapshot_date },
              { key: 'pair', title: '货币对', render: (r) => `${r.base_currency}/${r.quote_currency}` },
              { key: 'rate', title: '汇率', render: (r) => Number(r.rate).toFixed(6) },
              { key: 'src', title: '来源', render: (r) => r.source || '—' },
            ]}
          />
        </div>
      )}

      {/* Asset Price Tab */}
      {activeTab === 'prices' && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>资产价格管理</h3>
          <form onSubmit={handleAddPrice} style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 16, alignItems: 'flex-end' }}>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>资产代码</div>
              <input style={{ ...styles.input, width: 120 }} value={priceAsset} onChange={(e) => setPriceAsset(e.target.value.toUpperCase())} placeholder='00700.HK' required />
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>日期</div>
              <input type='date' style={styles.input} value={priceDate} onChange={(e) => setPriceDate(e.target.value)} required />
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>价格 (USD)</div>
              <input style={{ ...styles.input, width: 120 }} type='number' step='0.00000001' value={priceUsd} onChange={(e) => setPriceUsd(e.target.value)} placeholder='0.00' required />
            </div>
            <button style={styles.buttonPrimary} type='submit' disabled={priceSubmitting}>手动录入</button>
            <label style={{ ...styles.buttonSecondary, cursor: 'pointer' }}>
              批量 CSV
              <input type='file' accept='.csv' style={{ display: 'none' }} onChange={handlePriceCsv} />
            </label>
          </form>
          <div style={{ fontSize: 12, color: colors.muted, marginBottom: 8 }}>CSV 格式: asset_code,price_usd,price_date</div>
          <ProductTable
            emptyText='暂无价格记录'
            rows={prices}
            columns={[
              { key: 'date', title: '日期', render: (r) => r.snapshot_date },
              { key: 'asset', title: '资产代码', render: (r) => <strong>{r.asset_code}</strong> },
              { key: 'price', title: '价格 (USD)', render: (r) => Number(r.price_usd).toFixed(4) },
              { key: 'src', title: '来源', render: (r) => r.source || '—' },
            ]}
          />
        </div>
      )}

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

  try {
    const [usersResult, ratesResult, pricesResult] = await Promise.allSettled([
      canManage ? listAuthUsers(auth.accessToken) : Promise.resolve([]),
      getRates({ size: 100, accessToken: auth.accessToken }),
      getPrices({ size: 100, accessToken: auth.accessToken }),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        users: usersResult.status === 'fulfilled' ? (usersResult.value ?? []) : [],
        rates: ratesResult.status === 'fulfilled' ? (ratesResult.value?.items ?? []) : [],
        prices: pricesResult.status === 'fulfilled' ? (pricesResult.value?.items ?? []) : [],
      },
    };
  } catch (error) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        users: [],
        rates: [],
        prices: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
