import { useEffect, useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import {
  Client,
  Fund,
  NavRecord,
  ShareBalance,
  ShareTransaction,
  createShareRedemption,
  createShareSubscription,
  updateShareTransaction,
  deleteShareTransaction,
  getClients,
  getFunds,
  getNav,
  getShareBalances,
  getShareHistory,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  shares: ShareTransaction[];
  balances: ShareBalance[];
  funds: Fund[];
  clients: Client[];
  navRecords: NavRecord[];
  error?: string;
};

type FormMode = 'subscribe' | 'redeem';

export default function Page({ shares, balances, funds, clients, navRecords = [], error }: Props) {
  const { hasPermission, user } = useAuth();
  const { t } = useI18n();
  const { showToast } = useToast();
  const canWriteShares = hasPermission('shares.write');
  const isAdmin = user?.role === 'admin';

  const defaultFundId = String(funds[0]?.id ?? 1);
  const defaultClientId = String(clients[0]?.id ?? 1);

  const [rows, setRows] = useState(shares);
  const [balanceRows, setBalanceRows] = useState(balances);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [mode, setMode] = useState<FormMode>('subscribe');
  const [fundId, setFundId] = useState(defaultFundId);
  const [clientId, setClientId] = useState(defaultClientId);
  const lockedNavRecordsForFund = useMemo(
    () => navRecords.filter((r) => r.is_locked && String(r.fund_id) === fundId && r.nav_per_share > 0).sort((a, b) => b.nav_date.localeCompare(a.nav_date)),
    [navRecords, fundId],
  );
  const lockedNavDates = useMemo(() => lockedNavRecordsForFund.map((r) => r.nav_date), [lockedNavRecordsForFund]);
  const [txDate, setTxDate] = useState(() => {
    const first = navRecords.find((r) => r.is_locked);
    return first?.nav_date ?? '';
  });

  useEffect(() => {
    if (lockedNavDates.length > 0 && !lockedNavDates.includes(txDate)) {
      setTxDate(lockedNavDates[0]);
    } else if (lockedNavDates.length === 0) {
      setTxDate('');
    }
  }, [lockedNavDates]);
  const [amountUsd, setAmountUsd] = useState('500');
  const [submitting, setSubmitting] = useState(false);

  // Edit modal state
  const [editingTx, setEditingTx] = useState<ShareTransaction | null>(null);
  const [editTxDate, setEditTxDate] = useState('');
  const [editTxType, setEditTxType] = useState('');
  const [editAmountUsd, setEditAmountUsd] = useState('');
  const [editShares, setEditShares] = useState('');
  const [editNavAtDate, setEditNavAtDate] = useState('');
  const [editSubmitting, setEditSubmitting] = useState(false);

  const selectedBalance = useMemo(
    () => balanceRows.find((item) => item.fund_id === Number(fundId) && item.client_id === Number(clientId)),
    [balanceRows, clientId, fundId],
  );

  const fundMap = useMemo(() => Object.fromEntries(funds.map(f => [f.id, f.name])), [funds]);
  const clientMap = useMemo(() => Object.fromEntries(clients.map(c => [c.id, c.name])), [clients]);

  function openModal(newMode: FormMode) {
    setMode(newMode);
    setIsModalOpen(true);
  }

  function closeModal() {
    setIsModalOpen(false);
  }

  function openEdit(tx: ShareTransaction) {
    setEditTxDate(tx.tx_date);
    setEditTxType(tx.tx_type);
    setEditAmountUsd(String(tx.amount_usd));
    setEditShares(String(tx.shares));
    setEditNavAtDate(String(tx.nav_at_date));
    setEditingTx(tx);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWriteShares) {
      showToast(t('permissionDenied'), 'error');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        fund_id: Number(fundId),
        client_id: Number(clientId),
        tx_date: txDate,
        amount_usd: Number(amountUsd),
      };
      const created = mode === 'subscribe' ? await createShareSubscription(payload) : await createShareRedemption(payload);
      setRows((current) => {
        const merged = [created, ...current.filter((item) => item.id !== created.id)];
        return merged.sort((a, b) => (b.tx_date === a.tx_date ? b.id - a.id : b.tx_date.localeCompare(a.tx_date)));
      });

      const shareDelta = mode === 'subscribe' ? created.shares : -created.shares;
      setBalanceRows((current) => {
        const found = current.find((item) => item.fund_id === created.fund_id && item.client_id === created.client_id);
        if (!found) {
          return [...current, { fund_id: created.fund_id, client_id: created.client_id, share_balance: shareDelta }].sort(
            (a, b) => (a.fund_id === b.fund_id ? a.client_id - b.client_id : a.fund_id - b.fund_id),
          );
        }
        return current
          .map((item) =>
            item.fund_id === created.fund_id && item.client_id === created.client_id
              ? { ...item, share_balance: item.share_balance + shareDelta }
              : item,
          )
          .sort((a, b) => (a.fund_id === b.fund_id ? a.client_id - b.client_id : a.fund_id - b.fund_id));
      });
      showToast(mode === 'subscribe' ? t('subscriptionBooked', { clientId: created.client_id }) : t('redemptionBooked', { clientId: created.client_id }), 'success');
      closeModal();
    } catch (submitError) {
      showToast(submitError instanceof Error ? submitError.message : t('sharesFailed', { mode: mode === 'subscribe' ? t('subscribe') : t('redeem') }), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingTx) return;
    setEditSubmitting(true);
    try {
      const updated = await updateShareTransaction(editingTx.id, {
        tx_date: editTxDate,
        tx_type: editTxType,
        amount_usd: Number(editAmountUsd),
        shares: Number(editShares),
        nav_at_date: Number(editNavAtDate),
      });
      setRows(prev => prev.map(r => r.id === updated.id ? updated : r));
      setEditingTx(null);
      showToast('Share transaction updated.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to update.', 'error');
    } finally {
      setEditSubmitting(false);
    }
  }

  async function handleDelete(txId: number) {
    if (!confirm(t('confirmDeleteShareTx'))) return;
    try {
      await deleteShareTransaction(txId);
      setRows(prev => prev.filter(r => r.id !== txId));
      showToast('Share transaction deleted.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to delete.', 'error');
    }
  }

  return (
    <Layout title={t('sharesTitle')} subtitle={t('sharesSubtitle')} requiredPermission='shares.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16, gap: 10 }}>
        {canWriteShares && (
          <>
            <button style={{...styles.buttonPrimary, backgroundColor: colors.success}} onClick={() => openModal('subscribe')}>+ Subscribe</button>
            <button style={{...styles.buttonPrimary, backgroundColor: colors.danger}} onClick={() => openModal('redeem')}>- Redeem</button>
          </>
        )}
      </div>
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('rules')}</h3>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>{t('sharesRule1')}</li>
            <li>{t('sharesRule2')}</li>
            <li>{t('sharesRule3')}</li>
            <li>{t('sharesRule4')}</li>
          </ul>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('currentShareBalances')}</h3>
          <ProductTable
            emptyText={t('noAccountsFound')}
            rows={balanceRows}
            columns={[
              { key: 'fund', title: t('fund'), render: (item) => fundMap[item.fund_id] ?? `#${item.fund_id}` },
              { key: 'client', title: t('client'), render: (item) => clientMap[item.client_id] ?? `#${item.client_id}` },
              { key: 'balance', title: t('sharesLabel'), render: (item) => formatNumber(item.share_balance, 8) },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('shareLedger')}</h3>
        <ProductTable
          emptyText={t('noShareTransactions')}
          rows={rows}
          columns={[
            { key: 'date', title: t('date'), render: (item) => item.tx_date },
            { key: 'type', title: t('type'), render: (item) => {
              const c = item.tx_type === 'subscribe' ? '#16a34a' : item.tx_type === 'redeem' ? '#dc2626' : item.tx_type === 'seed' ? '#2563eb' : colors.text;
              return <span style={{ color: c, fontWeight: 600, fontSize: 12 }}>{item.tx_type}</span>;
            }},
            { key: 'fund', title: t('fund'), render: (item) => fundMap[item.fund_id] ?? `#${item.fund_id}` },
            { key: 'client', title: t('client'), render: (item) => item.client_id ? (clientMap[item.client_id] ?? `#${item.client_id}`) : '—' },
            { key: 'amount', title: t('amountUsd'), render: (item) => formatNumber(item.amount_usd) },
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.shares, 8) },
            { key: 'nav', title: 'NAV at Date', render: (item) => formatNumber(item.nav_at_date) },
            ...(isAdmin ? [{
              key: 'actions',
              title: '',
              render: (item: ShareTransaction) => (
                <div style={{ whiteSpace: 'nowrap' }}>
                  <button
                    style={{ ...styles.buttonSecondary, padding: '3px 8px', fontSize: 12, marginRight: 4 }}
                    onClick={() => openEdit(item)}
                  >
                    {t('editEntry')}
                  </button>
                  <button
                    style={{ ...styles.buttonSecondary, padding: '3px 8px', fontSize: 12, color: colors.danger, borderColor: colors.danger }}
                    onClick={() => handleDelete(item.id)}
                  >
                    {t('deleteEntry')}
                  </button>
                </div>
              ),
            }] : []),
          ]}
        />
      </div>

      {/* Subscribe / Redeem modal */}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={mode === 'subscribe' ? t('createSubscription') : t('createRedemption')}>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('fund')}>
            <select style={styles.input} value={fundId} onChange={(event) => setFundId(event.target.value)} disabled={submitting}>
              {funds.map((fund) => (
                <option key={fund.id} value={fund.id}>
                  #{fund.id} · {fund.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t('client')}>
            <select style={styles.input} value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={submitting}>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  #{client.id} · {client.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t('transactionDate')}>
            {lockedNavRecordsForFund.length > 0 ? (
              <select style={styles.input} value={txDate} onChange={(event) => setTxDate(event.target.value)} disabled={submitting}>
                {lockedNavRecordsForFund.map((r) => <option key={r.nav_date} value={r.nav_date}>{r.nav_date} (NAV: {formatNumber(r.nav_per_share)})</option>)}
              </select>
            ) : (
              <div style={{ color: colors.danger, fontSize: 13 }}>{t('noLockedNavDates')}</div>
            )}
          </FormField>
          <FormField label={t('amountUsd')}>
            <input style={styles.input} type='number' min='0' step='0.01' value={amountUsd} onChange={(event) => setAmountUsd(event.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ fontSize: 13, color: colors.muted, marginTop: 4 }}>
            {t('currentClientBalance')}: <strong>{formatNumber(selectedBalance?.share_balance ?? 0, 8)}</strong> {t('sharesLabel')}
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={closeModal} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('submitting') : mode === 'subscribe' ? t('createSubscription') : t('createRedemption')}
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit modal (admin only) */}
      <Modal isOpen={!!editingTx} onClose={() => setEditingTx(null)} title={t('editShareTx')}>
        <form onSubmit={handleEditSubmit} style={{ display: 'grid', gap: 12 }}>
          <FormField label={t('date')}>
            <input type="date" style={styles.input} value={editTxDate} onChange={e => setEditTxDate(e.target.value)} disabled={editSubmitting} required />
          </FormField>
          <FormField label={t('type')}>
            <select style={styles.input} value={editTxType} onChange={e => setEditTxType(e.target.value)} disabled={editSubmitting}>
              {['seed', 'subscribe', 'redeem'].map(tt => <option key={tt} value={tt}>{tt}</option>)}
            </select>
          </FormField>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <FormField label={t('amountUsd')}>
              <input type="number" step="any" style={styles.input} value={editAmountUsd} onChange={e => setEditAmountUsd(e.target.value)} disabled={editSubmitting} required />
            </FormField>
            <FormField label={t('sharesLabel')}>
              <input type="number" step="any" style={styles.input} value={editShares} onChange={e => setEditShares(e.target.value)} disabled={editSubmitting} required />
            </FormField>
          </div>
          <FormField label="NAV at Date">
            <input type="number" step="any" style={styles.input} value={editNavAtDate} onChange={e => setEditNavAtDate(e.target.value)} disabled={editSubmitting} required />
          </FormField>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" style={styles.buttonSecondary} onClick={() => setEditingTx(null)} disabled={editSubmitting}>{t('cancel')}</button>
            <button type="submit" style={styles.buttonPrimary} disabled={editSubmitting}>
              {editSubmitting ? t('saving') : t('saveAndNext')}
            </button>
          </div>
        </form>
      </Modal>

    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [shares, balances, fundData, clientData, navRecords] = await Promise.all([getShareHistory({ accessToken: auth.accessToken }), getShareBalances({ accessToken: auth.accessToken }), getFunds(1, 50, auth.accessToken), getClients({ accessToken: auth.accessToken }), getNav(undefined, auth.accessToken)]);
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, shares, balances, funds: fundData.items ?? [], clients: clientData.items ?? [], navRecords: navRecords ?? [] } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, shares: [], balances: [], funds: [], clients: [], navRecords: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
