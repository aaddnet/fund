import Link from 'next/link';
import { useMemo, useState } from 'react';
import Layout from '../components/Layout';

const BROKERS = [
  { value: 'moomoo', label: 'Moomoo / Futu' },
  { value: 'ib', label: 'Interactive Brokers' },
  { value: 'schwab', label: 'Charles Schwab' },
  { value: 'kraken', label: 'Kraken' },
  { value: 'other', label: 'Other' },
];
import ProductTable from '../components/ProductTable';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { Account, getAccounts, createAccount, updateAccount } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  rows: Account[];
  total: number;
  filters: {
    holder: string;
    broker: string;
    q: string;
  };
  error?: string;
};

export default function Page({ rows, total, filters, error }: Props) {
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canWrite = hasPermission('accounts.write');
  const activeFilterCount = useMemo(() => [filters.holder, filters.broker, filters.q].filter(Boolean).length, [filters]);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);

  const [holderName, setHolderName] = useState('');
  const [broker, setBroker] = useState('');
  const [accountNo, setAccountNo] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function openCreate() {
    setHolderName('');
    setBroker('');
    setAccountNo('');
    setIsCreateOpen(true);
  }

  function openEdit(account: Account) {
    setHolderName(account.holder_name || '');
    setBroker(account.broker);
    setAccountNo(account.account_no);
    setEditingAccount(account);
  }

  function closeModals() {
    setIsCreateOpen(false);
    setEditingAccount(null);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setSubmitting(true);
    try {
      await createAccount({ holder_name: holderName || undefined, broker, account_no: accountNo });
      showToast('Account created successfully', 'success');
      window.location.reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to create account', 'error');
      setSubmitting(false);
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite || !editingAccount) return;
    setSubmitting(true);
    try {
      await updateAccount(editingAccount.id, { holder_name: holderName || null, broker, account_no: accountNo });
      showToast('Account updated successfully', 'success');
      window.location.reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update account', 'error');
      setSubmitting(false);
    }
  }

  return (
    <Layout title={t('accountsTitle')} subtitle={t('accountsSubtitle')} requiredPermission='accounts.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        {canWrite && (
          <button style={styles.buttonPrimary} onClick={openCreate}>+ Create Account</button>
        )}
      </div>

      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('accountFilters')}</h3>
          <form method='get' style={{ display: 'grid', gap: 12 }}>
            <div>
              <label style={styles.label}>{t('accountHolder')}</label>
              <input name='holder' defaultValue={filters.holder} style={styles.input} placeholder={t('accountHolder')} />
            </div>
            <div>
              <label style={styles.label}>{t('brokerContains')}</label>
              <select name='broker' defaultValue={filters.broker} style={styles.input}>
                <option value=''>— All Brokers —</option>
                {BROKERS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}
              </select>
            </div>
            <div>
              <label style={styles.label}>{t('accountSearch')}</label>
              <input name='q' defaultValue={filters.q} style={styles.input} placeholder='ACC-001 / IB / ...' />
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type='submit' style={styles.buttonPrimary}>{t('applyFilters')}</button>
              <Link href='/accounts' style={{ ...styles.buttonSecondary, textDecoration: 'none' }}>{t('reset')}</Link>
            </div>
          </form>
        </div>

        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('summary')}</h3>
          <p style={{ marginBottom: 8 }}>{t('matchedAccounts')}: {total}</p>
          <p style={{ marginBottom: 8 }}>{t('activeFilters')}: {activeFilterCount}</p>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>{t('accountSummary1')}</li>
            <li>{t('accountSummary2')}</li>
            <li>{t('accountSummary3')}</li>
          </ul>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('liveAccountRegister')}</h3>
        <ProductTable
          emptyText={t('noAccountsForFilter')}
          rows={rows}
          columns={[
            { key: 'id', title: t('accountId'), render: (item) => <Link href={`/accounts/${item.id}`} style={{ color: colors.primary, fontWeight: 600 }}>#{item.id}</Link> },
            { key: 'holder', title: t('accountHolder'), render: (item) => item.holder_name || t('notAvailable') },
            { key: 'broker', title: 'Broker', render: (item) => item.broker },
            { key: 'account', title: 'Account No', render: (item) => <Link href={`/accounts/${item.id}`} style={{ color: colors.primary }}>{item.account_no}</Link> },
            { key: 'positions', title: t('currentPositions'), render: (item) => item.position_count },
            { key: 'transactions', title: t('transactions'), render: (item) => item.transaction_count },
            { key: 'trade', title: t('latestTrade'), render: (item) => item.latest_trade_date || t('notAvailable') },
            { key: 'snapshot', title: t('latestSnapshot'), render: (item) => item.latest_snapshot_date || t('notAvailable') },
            { key: 'snapValue', title: 'Snapshot Value (USD)', render: (item) => item.latest_snapshot_value_usd != null ? `$${item.latest_snapshot_value_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : t('notAvailable') },
            ...(canWrite ? [{
              key: 'actions', title: 'Actions', render: (item: Account) => (
                <button
                  style={{ ...styles.buttonSecondary, padding: '4px 8px', fontSize: 12 }}
                  onClick={() => openEdit(item)}
                >
                  Edit
                </button>
              )
            }] : [])
          ]}
        />
      </div>

      <Modal isOpen={isCreateOpen} onClose={closeModals} title="Create Account">
        <form onSubmit={handleCreate} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('accountHolder')}>
            <input style={styles.input} value={holderName} onChange={e => setHolderName(e.target.value)} placeholder={t('accountHolder')} disabled={submitting} />
          </FormField>
          <FormField label="Broker">
            <select required style={styles.input} value={broker} onChange={e => setBroker(e.target.value)} disabled={submitting}>
              <option value="">Select Broker</option>
              {BROKERS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}
            </select>
          </FormField>
          <FormField label="Account No">
            <input required style={styles.input} value={accountNo} onChange={e => setAccountNo(e.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type="submit">
              {submitting ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={!!editingAccount} onClose={closeModals} title="Edit Account">
        <form onSubmit={handleEdit} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('accountHolder')}>
            <input style={styles.input} value={holderName} onChange={e => setHolderName(e.target.value)} placeholder={t('accountHolder')} disabled={submitting} />
          </FormField>
          <FormField label="Broker">
            <select required style={styles.input} value={broker} onChange={e => setBroker(e.target.value)} disabled={submitting}>
              <option value="">Select Broker</option>
              {BROKERS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}
            </select>
          </FormField>
          <FormField label="Account No">
            <input required style={styles.input} value={accountNo} onChange={e => setAccountNo(e.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type="submit">
              {submitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </Modal>

    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const holder = typeof context.query.holder === 'string' ? context.query.holder : '';
  const broker = typeof context.query.broker === 'string' ? context.query.broker : '';
  const q = typeof context.query.q === 'string' ? context.query.q : '';

  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const accountData = await getAccounts({ accessToken: auth.accessToken, holder: holder || undefined, broker: broker || undefined, q: q || undefined });

    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: accountData.items ?? [],
        total: accountData.pagination?.total ?? accountData.items?.length ?? 0,
        filters: { holder, broker, q },
      },
    };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: [],
        total: 0,
        filters: { holder, broker, q },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
