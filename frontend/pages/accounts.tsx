import Link from 'next/link';
import { useMemo, useState } from 'react';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import FormField from '../components/FormField';
import { Account, Client, Fund, getAccounts, getClients, getFunds, createAccount } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  rows: Account[];
  total: number;
  funds: Fund[];
  clients: Client[];
  filters: {
    fundId: string;
    clientId: string;
    broker: string;
    q: string;
  };
  error?: string;
};

export default function Page({ rows, total, funds, clients, filters, error }: Props) {
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('accounts.write');
  const activeFilterCount = useMemo(() => [filters.fundId, filters.clientId, filters.broker, filters.q].filter(Boolean).length, [filters]);

  const [fundId, setFundId] = useState('');
  const [clientId, setClientId] = useState('');
  const [broker, setBroker] = useState('');
  const [accountNo, setAccountNo] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitState, setSubmitState] = useState('');

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setSubmitting(true);
    setSubmitState('');
    try {
      await createAccount({ fund_id: Number(fundId), client_id: Number(clientId), broker, account_no: accountNo });
      setSubmitState('Success! Refreshing...');
      window.location.reload();
    } catch (err) {
      setSubmitState(err instanceof Error ? err.message : 'Failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title={t('accountsTitle')} subtitle={t('accountsSubtitle')} requiredPermission='accounts.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Create Account</h3>
          <form onSubmit={handleCreate} style={{ display: 'grid', gap: 14 }}>
            <FormField label="Fund">
              <select required style={styles.input} value={fundId} onChange={e => setFundId(e.target.value)} disabled={!canWrite}>
                <option value="">Select Fund</option>
                {funds.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </FormField>
            <FormField label="Client">
              <select required style={styles.input} value={clientId} onChange={e => setClientId(e.target.value)} disabled={!canWrite}>
                <option value="">Select Client</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </FormField>
            <FormField label="Broker">
              <input required style={styles.input} value={broker} onChange={e => setBroker(e.target.value)} disabled={!canWrite} />
            </FormField>
            <FormField label="Account No">
              <input required style={styles.input} value={accountNo} onChange={e => setAccountNo(e.target.value)} disabled={!canWrite} />
            </FormField>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button style={styles.buttonPrimary} disabled={submitting || !canWrite} type="submit">
                {submitting ? 'Creating...' : 'Create Account'}
              </button>
              {submitState && <span style={{ color: submitState.includes('Success') ? colors.success : colors.danger }}>{submitState}</span>}
            </div>
          </form>
        </div>

        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('accountFilters')}</h3>
          <form method='get' style={{ display: 'grid', gap: 12 }}>
            <div>
              <label style={styles.label}>{t('fund')}</label>
              <select name='fundId' defaultValue={filters.fundId} style={styles.input}>
                <option value=''>{t('allFunds')}</option>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>{`#${fund.id} · ${fund.name}`}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={styles.label}>{t('client')}</label>
              <select name='clientId' defaultValue={filters.clientId} style={styles.input}>
                <option value=''>{t('allClients')}</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{`#${client.id} · ${client.name}`}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={styles.label}>{t('brokerContains')}</label>
              <input name='broker' defaultValue={filters.broker} style={styles.input} placeholder='IB / HK Broker / ...' />
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
            { key: 'id', title: t('accountId'), render: (item) => item.id },
            { key: 'fund', title: t('fund'), render: (item) => item.fund_name || `Fund #${item.fund_id}` },
            { key: 'client', title: t('client'), render: (item) => item.client_name || (item.client_id ? `Client #${item.client_id}` : t('notAvailable')) },
            { key: 'broker', title: 'Broker', render: (item) => item.broker },
            { key: 'account', title: 'Account No', render: (item) => item.account_no },
            { key: 'positions', title: t('currentPositions'), render: (item) => item.position_count },
            { key: 'transactions', title: t('transactions'), render: (item) => item.transaction_count },
            { key: 'trade', title: t('latestTrade'), render: (item) => item.latest_trade_date || t('notAvailable') },
            { key: 'snapshot', title: t('latestSnapshot'), render: (item) => item.latest_snapshot_date || t('notAvailable') },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const fundId = typeof context.query.fundId === 'string' ? context.query.fundId : '';
  const clientId = typeof context.query.clientId === 'string' ? context.query.clientId : '';
  const broker = typeof context.query.broker === 'string' ? context.query.broker : '';
  const q = typeof context.query.q === 'string' ? context.query.q : '';

  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [accountData, fundData, clientData] = await Promise.all([
      getAccounts({ accessToken: auth.accessToken, fundId: fundId ? Number(fundId) : undefined, clientId: clientId ? Number(clientId) : undefined, broker: broker || undefined, q: q || undefined }),
      getFunds(1, 50, auth.accessToken),
      getClients({ accessToken: auth.accessToken }),
    ]);

    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: accountData.items ?? [],
        total: accountData.pagination?.total ?? accountData.items?.length ?? 0,
        funds: fundData.items ?? [],
        clients: clientData.items ?? [],
        filters: { fundId, clientId, broker, q },
      },
    };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: [],
        total: 0,
        funds: [],
        clients: [],
        filters: { fundId, clientId, broker, q },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
