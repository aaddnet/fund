import Layout from '../components/Layout';
import { getShareHistory, ShareTransaction } from '../lib/api';

type Props = {
  shares: ShareTransaction[];
  error?: string;
};

export default function Page({ shares, error }: Props) {
  return (
    <Layout title='Share Transactions'>
      {error ? <p style={{ color: 'crimson' }}>Backend warning: {error}</p> : null}
      {shares.length === 0 ? (
        <p>No share transactions found.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th align='left'>Date</th>
              <th align='left'>Type</th>
              <th align='left'>Fund</th>
              <th align='left'>Client</th>
              <th align='left'>Amount USD</th>
              <th align='left'>Shares</th>
              <th align='left'>NAV at Date</th>
            </tr>
          </thead>
          <tbody>
            {shares.map((item) => (
              <tr key={item.id}>
                <td>{item.tx_date}</td>
                <td>{item.tx_type}</td>
                <td>{item.fund_id}</td>
                <td>{item.client_id}</td>
                <td>{item.amount_usd}</td>
                <td>{item.shares}</td>
                <td>{item.nav_at_date}</td>
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
    return { props: { shares: await getShareHistory() } };
  } catch (error) {
    return {
      props: {
        shares: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
