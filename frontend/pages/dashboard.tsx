import Layout from '../components/Layout';
import { getFees, getHealth, getHealthDb, getNav, getShareHistory, NavRecord, FeeRecord, ShareTransaction } from '../lib/api';

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
    <Layout title='Dashboard'>
      {error ? <p style={{ color: 'crimson' }}>Backend warning: {error}</p> : null}
      <ul>
        <li>API health: {health}</li>
        <li>Database health: {db}</li>
        <li>Latest NAV: {latestNav ? `${latestNav.nav_per_share} on ${latestNav.nav_date}` : 'No NAV records yet'}</li>
        <li>Share transactions: {shares.length}</li>
        <li>Fee records: {fees.length}</li>
      </ul>
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

    return {
      props: {
        health: health.status,
        db: db.db,
        nav,
        shares,
        fees,
      },
    };
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
