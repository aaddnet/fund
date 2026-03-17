import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { Account, getAccounts } from '../lib/api';
import { styles } from '../lib/ui';

type Props = {
  rows: Account[];
  total: number;
  error?: string;
};

export default function Page({ rows, total, error }: Props) {
  return (
    <Layout title='Accounts' subtitle='Read live account records from the backend, including recent snapshot coverage and activity counts.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Account Registry</h3>
          <p style={{ marginBottom: 8 }}>Total accounts: {total}</p>
          <p style={{ color: '#64748b', marginBottom: 0 }}>
            This page now uses the real `/account` list endpoint. It is read-only in this batch, but the data comes from live funds, clients, positions, and transactions.
          </p>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Operational Notes</h3>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>Accounts are tied to funds via <code>fund_id</code>.</li>
            <li>Snapshot coverage shows the latest available <code>position.snapshot_date</code>.</li>
            <li>Counts help quickly identify active vs dormant accounts.</li>
          </ul>
        </div>
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Live Account Register</h3>
        <ProductTable
          emptyText='No accounts found.'
          rows={rows}
          columns={[
            { key: 'id', title: 'Account ID', render: (item) => item.id },
            { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
            { key: 'client', title: 'Client', render: (item) => item.client_id ?? '—' },
            { key: 'broker', title: 'Broker', render: (item) => item.broker },
            { key: 'account', title: 'Account No', render: (item) => item.account_no },
            { key: 'positions', title: 'Positions', render: (item) => item.position_count },
            { key: 'transactions', title: 'Transactions', render: (item) => item.transaction_count },
            { key: 'snapshot', title: 'Latest Snapshot', render: (item) => item.latest_snapshot_date || '—' },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const data = await getAccounts();
    return { props: { rows: data.items ?? [], total: data.pagination?.total ?? data.items?.length ?? 0 } };
  } catch (error) {
    return { props: { rows: [], total: 0, error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
