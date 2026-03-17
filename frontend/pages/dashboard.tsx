import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import StatCard from '../components/StatCard';
import { getFees, getHealth, getHealthDb, getNav, getShareHistory, NavRecord, FeeRecord, ShareTransaction } from '../lib/api';
import { formatNumber, styles } from '../lib/ui';

type Props = {
  health: string;
  db: string;
  nav: NavRecord[];
  shares: ShareTransaction[];
  fees: FeeRecord[];
  error?: string;
};

export default function Page({ health, db, nav, shares, fees, error }: Props) {
  const latestNav = nav[0];

  return (
    <Layout title='Operations Dashboard' subtitle='Executive view of service health, NAV, subscriptions, and fee activity.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}

      <div style={styles.grid3}>
        <StatCard label='API Health' value={health.toUpperCase()} tone={health === 'ok' ? 'success' : 'warning'} />
        <StatCard label='Database' value={db.toUpperCase()} tone={db === 'ok' ? 'success' : 'warning'} />
        <StatCard label='Latest NAV' value={latestNav ? formatNumber(latestNav.nav_per_share) : '—'} hint={latestNav ? latestNav.nav_date : 'No NAV records yet'} />
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
    const [health, db, nav, shares, fees] = await Promise.all([
      getHealth(),
      getHealthDb(),
      getNav(),
      getShareHistory(),
      getFees(),
    ]);

    return { props: { health: health.status, db: db.db, nav, shares, fees } };
  } catch (error) {
    return {
      props: {
        health: 'error',
        db: 'error',
        nav: [],
        shares: [],
        fees: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
