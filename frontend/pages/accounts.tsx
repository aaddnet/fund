import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { getPlaceholderResource } from '../lib/api';
import { styles } from '../lib/ui';

type AccountDraft = {
  id: number;
  fundId: string;
  clientId: string;
  broker: string;
  accountNo: string;
  status: string;
};

type Props = {
  total: number;
  error?: string;
};

export default function Page({ total, error }: Props) {
  const [rows, setRows] = useState<AccountDraft[]>([
    { id: 1, fundId: '1', clientId: '1', broker: 'Interactive Brokers', accountNo: 'ACC-001', status: 'Active' },
    { id: 2, fundId: '1', clientId: '—', broker: 'Kraken', accountNo: 'CRYPTO-01', status: 'Pending review' },
  ]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const current = useMemo(() => rows.find((item) => item.id === editingId), [rows, editingId]);
  const [form, setForm] = useState({ fundId: '1', clientId: '', broker: '', accountNo: '', status: 'Draft' });

  function resetForm() {
    setEditingId(null);
    setForm({ fundId: '1', clientId: '', broker: '', accountNo: '', status: 'Draft' });
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingId) {
      setRows((items) => items.map((item) => (item.id === editingId ? { id: editingId, ...form } : item)));
    } else {
      setRows((items) => [{ id: Date.now(), ...form }, ...items]);
    }
    resetForm();
  }

  function startEdit(row: AccountDraft) {
    setEditingId(row.id);
    setForm({ fundId: row.fundId, clientId: row.clientId, broker: row.broker, accountNo: row.accountNo, status: row.status });
  }

  return (
    <Layout title='Accounts' subtitle='Maintain operational account records with an internal draft workflow while backend CRUD is pending.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{editingId ? 'Edit Account Draft' : 'Create Account Draft'}</h3>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14 }}>
            <FormField label='Fund ID'><input style={styles.input} value={form.fundId} onChange={(e) => setForm({ ...form, fundId: e.target.value })} /></FormField>
            <FormField label='Client ID'><input style={styles.input} value={form.clientId} onChange={(e) => setForm({ ...form, clientId: e.target.value })} /></FormField>
            <FormField label='Broker'><input style={styles.input} value={form.broker} onChange={(e) => setForm({ ...form, broker: e.target.value })} /></FormField>
            <FormField label='Account No'><input style={styles.input} value={form.accountNo} onChange={(e) => setForm({ ...form, accountNo: e.target.value })} /></FormField>
            <FormField label='Status'><input style={styles.input} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} /></FormField>
            <div style={{ display: 'flex', gap: 10 }}>
              <button style={styles.buttonPrimary} type='submit'>{editingId ? 'Save Changes' : 'Create Draft'}</button>
              <button style={styles.buttonSecondary} type='button' onClick={resetForm}>Reset</button>
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Backend Status</h3>
          <p>Placeholder account endpoint total: {total}</p>
          <p style={{ color: '#64748b' }}>Until account CRUD endpoints are implemented, this page provides a realistic front-end create/edit workflow for product review and UX validation.</p>
          {current ? <p style={{ marginBottom: 0 }}>Editing: {current.broker} / {current.accountNo}</p> : null}
        </div>
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Draft Account Register</h3>
        <ProductTable
          emptyText='No account drafts yet.'
          rows={rows}
          columns={[
            { key: 'fund', title: 'Fund', render: (item) => item.fundId },
            { key: 'client', title: 'Client', render: (item) => item.clientId || '—' },
            { key: 'broker', title: 'Broker', render: (item) => item.broker },
            { key: 'account', title: 'Account No', render: (item) => item.accountNo },
            { key: 'status', title: 'Status', render: (item) => item.status },
            { key: 'action', title: 'Action', render: (item) => <button style={styles.buttonSecondary} onClick={() => startEdit(item)}>Edit</button> },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const data = await getPlaceholderResource('/account');
    return { props: { total: data.pagination?.total ?? data.items?.length ?? 0 } };
  } catch (error) {
    return { props: { total: 0, error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
