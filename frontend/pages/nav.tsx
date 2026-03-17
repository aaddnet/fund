import Layout from '../components/Layout';
import { getNav, NavRecord } from '../lib/api';

type Props = {
  nav: NavRecord[];
  error?: string;
};

export default function Page({ nav, error }: Props) {
  return (
    <Layout title='NAV Records'>
      {error ? <p style={{ color: 'crimson' }}>Backend warning: {error}</p> : null}
      {nav.length === 0 ? (
        <p>No NAV records found.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th align='left'>Date</th>
              <th align='left'>Fund</th>
              <th align='left'>Assets USD</th>
              <th align='left'>Shares</th>
              <th align='left'>NAV / Share</th>
              <th align='left'>Locked</th>
            </tr>
          </thead>
          <tbody>
            {nav.map((item) => (
              <tr key={item.id}>
                <td>{item.nav_date}</td>
                <td>{item.fund_id}</td>
                <td>{item.total_assets_usd}</td>
                <td>{item.total_shares}</td>
                <td>{item.nav_per_share}</td>
                <td>{item.is_locked ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    return { props: { nav: await getNav() } };
  } catch (error) {
    return {
      props: {
        nav: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
