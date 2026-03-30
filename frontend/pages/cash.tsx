import { useMemo, useState } from 'react';
import Layout from '../components/Layout';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { Account, CashPosition, Fund, getCashPositions, upsertCashPosition, deleteCashPosition, getAccounts, getFunds } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  rows: CashPosition[];
  accounts: Account[];
  funds: Fund[];
  error?: string;
};

export default function Page({ rows: initialRows, accounts, funds, error }: Props) {
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canWrite = hasPermission('nav.write');

  const [rows, setRows] = useState<CashPosition[]>(initialRows);
  const [isOpen, setIsOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [accountId, setAccountId] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [amount, setAmount] = useState('');
  const [snapshotDate, setSnapshotDate] = useState('');
  const [note, setNote] = useState('');

  const [filterFundId, setFilterFundId] = useState('');
  const [filterDate, setFilterDate] = useState('');

  const accountMap = useMemo(() => Object.fromEntries(accounts.map(a => [a.id, a])), [accounts]);
  const fundMap = useMemo(() => Object.fromEntries(funds.map(f => [f.id, f])), [funds]);

  const filteredAccounts = useMemo(() => {
    if (!filterFundId) return accounts;
    return accounts.filter(a => String(a.fund_id) === filterFundId);
  }, [accounts, filterFundId]);

  const filteredRows = useMemo(() => {
    return rows.filter(r => {
      if (filterFundId) {
        const acct = accountMap[r.account_id];
        if (!acct || String(acct.fund_id) !== filterFundId) return false;
      }
      if (filterDate && r.snapshot_date !== filterDate) return false;
      return true;
    });
  }, [rows, filterFundId, filterDate, accountMap]);

  function openCreate() {
    setEditingId(null);
    setAccountId('');
    setCurrency('USD');
    setAmount('');
    setSnapshotDate('');
    setNote('');
    setIsOpen(true);
  }

  function openEdit(row: CashPosition) {
    setEditingId(row.id);
    setAccountId(String(row.account_id));
    setCurrency(row.currency);
    setAmount(String(row.amount));
    setSnapshotDate(row.snapshot_date);
    setNote(row.note || '');
    setIsOpen(true);
  }

  function closeModal() {
    setIsOpen(false);
    setEditingId(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId || !currency || !amount || !snapshotDate) return;
    setSubmitting(true);
    try {
      const saved = await upsertCashPosition({
        account_id: Number(accountId),
        currency: currency.toUpperCase(),
        amount: Number(amount),
        snapshot_date: snapshotDate,
        note: note || null,
      });
      setRows(prev => {
        const idx = prev.findIndex(r => r.id === saved.id);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = saved;
          return next;
        }
        return [saved, ...prev];
      });
      showToast(`Saved cash position: ${currency} ${amount}`, 'success');
      closeModal();
    } catch (err: any) {
      showToast(err.message || 'Failed to save.', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('Delete this cash position?')) return;
    try {
      await deleteCashPosition(id);
      setRows(prev => prev.filter(r => r.id !== id));
      showToast('Deleted.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to delete.', 'error');
    }
  }

  const accountLabel = (acctId: number) => {
    const a = accountMap[acctId];
    if (!a) return `Account #${acctId}`;
    const f = fundMap[a.fund_id];
    return `${a.account_no} (${a.broker}${f ? ` · ${f.name}` : ''})`;
  };

  return (
    <Layout title={t('cashTitle')} subtitle={t('cashSubtitle')} requiredPermission="nav.read">
      {error ? <div style={{ ...styles.card, color: colors.danger, marginBottom: 16 }}>{error}</div> : null}

      <div style={{ ...styles.card, marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <FormField label={t('fund')}>
          <select style={{ ...styles.input, width: 160 }} value={filterFundId} onChange={e => setFilterFundId(e.target.value)}>
            <option value="">{t('allFunds')}</option>
            {funds.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('snapshotDate')}>
          <input type="date" style={{ ...styles.input, width: 160 }} value={filterDate} onChange={e => setFilterDate(e.target.value)} />
        </FormField>
        {canWrite && (
          <button style={{ ...styles.buttonPrimary, marginBottom: 2 }} onClick={openCreate}>{t('addCashPosition')}</button>
        )}
      </div>

      <div style={styles.card}>
        {filteredRows.length === 0 ? (
          <p style={{ color: colors.muted }}>{t('noCashPositions')}</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                {['Account', t('currency'), t('amount'), t('snapshotDate'), t('note'), canWrite ? t('actions') : null]
                  .filter(Boolean)
                  .map((h, i) => <th key={i} style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 600 }}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map(row => (
                <tr key={row.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                  <td style={{ padding: '8px 10px' }}>{accountLabel(row.account_id)}</td>
                  <td style={{ padding: '8px 10px' }}>{row.currency}</td>
                  <td style={{ padding: '8px 10px' }}>{Number(row.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                  <td style={{ padding: '8px 10px' }}>{row.snapshot_date}</td>
                  <td style={{ padding: '8px 10px', color: colors.muted }}>{row.note || '—'}</td>
                  {canWrite && (
                    <td style={{ padding: '8px 10px' }}>
                      <button style={{ ...styles.buttonSecondary, fontSize: 12, padding: '4px 8px', marginRight: 6 }} onClick={() => openEdit(row)}>Edit</button>
                      <button style={{ ...styles.buttonSecondary, fontSize: 12, padding: '4px 8px', color: colors.danger }} onClick={() => handleDelete(row.id)}>Delete</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal isOpen={isOpen} onClose={closeModal} title={editingId ? 'Edit Cash Position' : t('addCashPosition')}>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14 }}>
          <FormField label="Account">
            <select required style={styles.input} value={accountId} onChange={e => setAccountId(e.target.value)} disabled={submitting}>
              <option value="">Select Account</option>
              {filteredAccounts.map(a => <option key={a.id} value={a.id}>{a.account_no} ({a.broker})</option>)}
            </select>
          </FormField>
          <FormField label={t('currency')}>
            <input required style={styles.input} value={currency} onChange={e => setCurrency(e.target.value.toUpperCase())} maxLength={10} disabled={submitting} />
          </FormField>
          <FormField label={t('amount')}>
            <input required type="number" step="any" style={styles.input} value={amount} onChange={e => setAmount(e.target.value)} disabled={submitting} />
          </FormField>
          <FormField label={t('snapshotDate')}>
            <input required type="date" style={styles.input} value={snapshotDate} onChange={e => setSnapshotDate(e.target.value)} disabled={submitting} />
          </FormField>
          <FormField label={t('note')}>
            <input style={styles.input} value={note} onChange={e => setNote(e.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 4 }}>
            <button type="button" onClick={closeModal} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type="submit">
              {submitting ? 'Saving...' : 'Save'}
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

  try {
    const [cashData, accountData, fundData] = await Promise.all([
      getCashPositions({ accessToken: auth.accessToken }),
      getAccounts({ accessToken: auth.accessToken, size: 200 }),
      getFunds(1, 100, auth.accessToken),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        rows: cashData ?? [],
        accounts: accountData.items ?? [],
        funds: fundData.items ?? [],
      },
    };
  } catch (error: any) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        rows: [],
        accounts: [],
        funds: [],
        error: error?.message || 'Failed to load cash positions.',
      },
    };
  }
}
