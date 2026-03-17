import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { Client, getClients } from '../lib/api';
import { styles } from '../lib/ui';

type Props = {
  rows: Client[];
  total: number;
  error?: string;
};

export default function Page({ rows, total, error }: Props) {
  return (
    <Layout title='Clients' subtitle='Review live client master data from the backend.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Client Register</h3>
          <p style={{ marginBottom: 0 }}>Total clients: {total}</p>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Batch Scope</h3>
          <p style={{ color: '#64748b', marginBottom: 0 }}>This page is read-only for now, but it no longer depends on placeholder data.</p>
        </div>
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Live Clients</h3>
        <ProductTable
          emptyText='No clients found.'
          rows={rows}
          columns={[
            { key: 'id', title: 'Client ID', render: (item) => item.id },
            { key: 'name', title: 'Name', render: (item) => item.name },
            { key: 'email', title: 'Email', render: (item) => item.email || '—' },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const data = await getClients();
    return { props: { rows: data.items ?? [], total: data.pagination?.total ?? data.items?.length ?? 0 } };
  } catch (error) {
    return { props: { rows: [], total: 0, error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
