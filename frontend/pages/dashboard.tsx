import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import StatCard from '../components/StatCard';
import TrendChart from '../components/TrendChart';
import Link from 'next/link';
import { useAuth } from '../lib/auth';
import { getAccounts, getHealth, getHealthDb, getNav, getPositions, getTransactions, Account, NavRecord, Position, Transaction } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { formatNumber, styles, colors } from '../lib/ui';

type Props = {
  health: string;
  db: string;
  nav: NavRecord[];
  transactions: Transaction[];
  accounts: Account[];
  positions: Position[];
  error?: string;
};

export default function Page({ health, db, nav, transactions, accounts, positions, error }: Props) {
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const latestNav = nav[0];
  const latestSnapshotDate = positions[0]?.snapshot_date ?? t('notAvailable');
  const totalPositions = positions.length;

  const navTrendData = nav.slice(0, 10).reverse().map(item => ({
    label: item.nav_date,
    value: item.nav_per_share
  }));

  return (
    <Layout title={t('dashboardTitle')} subtitle={t('dashboardSubtitle')} requiredPermission='dashboard.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>{t('backendWarning')}: {error}</div> : null}

      {/* Quick Actions Row */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        {hasPermission('nav.write') && (
          <Link href="/nav" style={{ ...styles.buttonPrimary, textDecoration: 'none', backgroundColor: colors.success }}>+ Calculate NAV</Link>
        )}
        {hasPermission('import.write') && (
          <Link href="/import" style={{ ...styles.buttonPrimary, textDecoration: 'none', backgroundColor: colors.primary }}>+ Upload CSV</Link>
        )}
        {hasPermission('accounts.write') && (
          <Link href="/accounts" style={{ ...styles.buttonSecondary, textDecoration: 'none' }}>+ New Account</Link>
        )}
      </div>

      <div style={styles.grid3}>
        <StatCard label={t('apiHealth')} value={health.toUpperCase()} tone={health === 'ok' ? 'success' : 'warning'} />
        <StatCard label={t('database')} value={db.toUpperCase()} tone={db === 'ok' ? 'success' : 'warning'} />
        <StatCard label={t('latestNav')} value={latestNav ? formatNumber(latestNav.nav_per_share) : t('notAvailable')} hint={latestNav ? latestNav.nav_date : t('noNavRecords')} />
      </div>

      <div style={{ ...styles.grid3, marginTop: 16 }}>
        <StatCard label={t('accountsCount')} value={String(accounts.length)} hint='Live /account endpoint' />
        <StatCard label={t('currentPositions')} value={String(totalPositions)} hint={latestSnapshotDate !== t('notAvailable') ? `${t('latestSnapshot')} ${latestSnapshotDate}` : t('noPositionsFound')} />
        <StatCard label={t('transactions')} value={String(transactions.length)} hint='Recent transactions' />
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>NAV Trend (Last 10)</h3>
          <TrendChart data={navTrendData} />
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('recentNavRecords')}</h3>
          <ProductTable
            emptyText={t('noNavRecords')}
            rows={nav.slice(0, 5)}
            columns={[
              { key: 'date', title: t('date'), render: (item) => item.nav_date },
              { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.nav_per_share) },
              { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.total_assets_usd) },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('recentAccounts')}</h3>
          <ProductTable
            emptyText={t('noAccountsFound')}
            rows={accounts.slice(0, 5)}
            columns={[
              { key: 'id', title: t('accountId'), render: (item) => item.id },
              { key: 'broker', title: 'Broker', render: (item) => item.broker },
              { key: 'acct', title: 'Account No', render: (item) => item.account_no },
              { key: 'snapshot', title: t('latestSnapshot'), render: (item) => item.latest_snapshot_date || t('notAvailable') },
            ]}
          />
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('transactions')}</h3>
          <ProductTable
            emptyText='No recent transactions'
            rows={transactions.slice(0, 5)}
            columns={[
              { key: 'date', title: t('date'), render: (item) => item.trade_date },
              { key: 'type', title: t('type'), render: (item) => item.tx_type },
              { key: 'asset', title: 'Asset', render: (item) => item.asset_code || '—' },
              { key: 'qty', title: t('quantity'), render: (item) => item.quantity != null ? formatNumber(item.quantity) : '—' },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('latestPositionSnapshot')}</h3>
        <ProductTable
          emptyText={t('noPositionsFound')}
          rows={positions.slice(0, 5)}
          columns={[
            { key: 'date', title: 'Snapshot Date', render: (item) => item.snapshot_date },
            { key: 'account', title: t('accountId'), render: (item) => item.account_id },
            { key: 'asset', title: 'Asset', render: (item) => item.asset_code },
            { key: 'qty', title: t('quantity'), render: (item) => formatNumber(item.quantity, 8) },
            { key: 'ccy', title: t('currency'), render: (item) => item.currency },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [health, db, nav, accountData, positionData, transactionData] = await Promise.all([
      getHealth(auth.accessToken),
      getHealthDb(auth.accessToken),
      getNav(auth.accessToken),
      getAccounts({ accessToken: auth.accessToken }),
      getPositions({ size: 20, accessToken: auth.accessToken }),
      getTransactions({ size: 10, accessToken: auth.accessToken }),
    ]);

    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, health: health.status, db: db.db, nav, transactions: transactionData.items ?? [], accounts: accountData.items ?? [], positions: positionData.items ?? [] } };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        health: 'error',
        db: 'error',
        nav: [],
        transactions: [],
        accounts: [],
        positions: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
