import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import StatCard from '../components/StatCard';
import { getAccounts, getFees, getHealth, getHealthDb, getNav, getPositions, getShareHistory, Account, NavRecord, FeeRecord, Position, ShareTransaction } from '../lib/api';
import { formatNumber, styles } from '../lib/ui';

type Props = {
  health: string;
  db: string;
  nav: NavRecord[];
  shares: ShareTransaction[];
  fees: FeeRecord[];
  accounts: Account[];
  positions: Position[];
  error?: string;
};

export default function Page({ health, db, nav, shares, fees, accounts, positions, error }: Props) {
  const latestNav = nav[0];
  const latestSnapshotDate = positions[0]?.snapshot_date ?? '—';
  const totalPositions = positions.length;

  return (
    <Layout title='Operations Dashboard' subtitle='Executive view of service health, NAV, accounts, and recent operational activity.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}

      <div style={styles.grid3}>
        <StatCard label='API Health' value={health.toUpperCase()} tone={health === 'ok' ? 'success' : 'warning'} />
        <StatCard label='Database' value={db.toUpperCase()} tone={db === 'ok' ? 'success' : 'warning'} />
        <StatCard label='Latest NAV' value={latestNav ? formatNumber(latestNav.nav_per_share) : '—'} hint={latestNav ? latestNav.nav_date : 'No NAV records yet'} />
      </div>

      <div style={{ ...styles.grid3, marginTop: 16 }}>
        <StatCard label='Accounts' value={String(accounts.length)} hint='Live /account endpoint' />
        <StatCard label='Current Positions' value={String(totalPositions)} hint={latestSnapshotDate !== '—' ? `Latest snapshot ${latestSnapshotDate}` : 'No position snapshots'} />
        <StatCard label='Share Events' value={String(shares.length)} hint='Subscriptions / redemptions' />
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Recent NAV Records</h3>
          <ProductTable
            emptyText='No NAV records found.'
            rows={nav.slice(0, 5)}
            columns={[
              { key: 'date', title: 'Date', render: (item) => item.nav_date },
              { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
              { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.nav_per_share) },
              { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.total_assets_usd) },
            ]}
          />
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Recent Accounts</h3>
          <ProductTable
            emptyText='No accounts found.'
            rows={accounts.slice(0, 5)}
            columns={[
              { key: 'id', title: 'Account', render: (item) => item.id },
              { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
              { key: 'broker', title: 'Broker', render: (item) => item.broker },
              { key: 'acct', title: 'Account No', render: (item) => item.account_no },
              { key: 'snapshot', title: 'Latest Snapshot', render: (item) => item.latest_snapshot_date || '—' },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Recent Share Transactions</h3>
          <ProductTable
            emptyText='No share transactions found.'
            rows={shares.slice(0, 5)}
            columns={[
              { key: 'date', title: 'Date', render: (item) => item.tx_date },
              { key: 'type', title: 'Type', render: (item) => item.tx_type },
              { key: 'amount', title: 'Amount USD', render: (item) => formatNumber(item.amount_usd) },
              { key: 'shares', title: 'Shares', render: (item) => formatNumber(item.shares, 8) },
            ]}
          />
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Latest Position Snapshot</h3>
          <ProductTable
            emptyText='No positions found.'
            rows={positions.slice(0, 5)}
            columns={[
              { key: 'date', title: 'Snapshot Date', render: (item) => item.snapshot_date },
              { key: 'account', title: 'Account', render: (item) => item.account_id },
              { key: 'asset', title: 'Asset', render: (item) => item.asset_code },
              { key: 'qty', title: 'Quantity', render: (item) => formatNumber(item.quantity, 8) },
              { key: 'ccy', title: 'Currency', render: (item) => item.currency },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Fee Records</h3>
        <ProductTable
          emptyText='No fee records found.'
          rows={fees}
          columns={[
            { key: 'date', title: 'Fee Date', render: (item) => item.fee_date },
            { key: 'gross', title: 'Gross Return', render: (item) => `${formatNumber(item.gross_return, 5)}` },
            { key: 'rate', title: 'Fee Rate', render: (item) => `${formatNumber(item.fee_rate, 4)}` },
            { key: 'amount', title: 'Amount USD', render: (item) => formatNumber(item.fee_amount_usd) },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const [health, db, nav, shares, fees, accountData, positionData] = await Promise.all([
      getHealth(),
      getHealthDb(),
      getNav(),
      getShareHistory(),
      getFees(),
      getAccounts(),
      getPositions({ size: 20 }),
    ]);

    return { props: { health: health.status, db: db.db, nav, shares, fees, accounts: accountData.items ?? [], positions: positionData.items ?? [] } };
  } catch (error) {
    return {
      props: {
        health: 'error',
        db: 'error',
        nav: [],
        shares: [],
        fees: [],
        accounts: [],
        positions: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
