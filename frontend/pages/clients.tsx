import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { getPlaceholderResource } from '../lib/api';
import { styles } from '../lib/ui';

type ClientDraft = {
  id: number;
  name: string;
  email: string;
  segment: string;
  owner: string;
};

type Props = {
  total: number;
  error?: string;
};

export default function Page({ total, error }: Props) {
  const [rows, setRows] = useState<ClientDraft[]>([
    { id: 1, name: 'Alice Capital', email: 'alice@example.com', segment: 'HNWI', owner: 'Seven' },
    { id: 2, name: 'Beta Family Office', email: 'beta@example.com', segment: 'Institutional', owner: 'Ops' },
  ]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const current = useMemo(() => rows.find((item) => item.id === editingId), [rows, editingId]);
  const [form, setForm] = useState({ name: '', email: '', segment: 'HNWI', owner: 'Seven' });

  function resetForm() {
    setEditingId(null);
    setForm({ name: '', email: '', segment: 'HNWI', owner: 'Seven' });
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

  function startEdit(row: ClientDraft) {
    setEditingId(row.id);
    setForm({ name: row.name, email: row.email, segment: row.segment, owner: row.owner });
  }

  return (
    <Layout title='Clients' subtitle='Capture investor-facing client details in a polished draft workspace.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{editingId ? 'Edit Client Draft' : 'Create Client Draft'}</h3>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14 }}>
            <FormField label='Client Name'><input style={styles.input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></FormField>
            <FormField label='Email'><input style={styles.input} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></FormField>
            <FormField label='Segment'><input style={styles.input} value={form.segment} onChange={(e) => setForm({ ...form, segment: e.target.value })} /></FormField>
            <FormField label='Relationship Owner'><input style={styles.input} value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} /></FormField>
            <div style={{ display: 'flex', gap: 10 }}>
              <button style={styles.buttonPrimary} type='submit'>{editingId ? 'Save Changes' : 'Create Draft'}</button>
              <button style={styles.buttonSecondary} type='button' onClick={resetForm}>Reset</button>
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Backend Status</h3>
          <p>Placeholder client endpoint total: {total}</p>
          <p style={{ color: '#64748b' }}>This create/edit experience is production-style UI scaffolding while backend write endpoints are still placeholder-only.</p>
          {current ? <p style={{ marginBottom: 0 }}>Editing: {current.name}</p> : null}
        </div>
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Client Drafts</h3>
        <ProductTable
          emptyText='No client drafts yet.'
          rows={rows}
          columns={[
            { key: 'name', title: 'Name', render: (item) => item.name },
            { key: 'email', title: 'Email', render: (item) => item.email },
            { key: 'segment', title: 'Segment', render: (item) => item.segment },
            { key: 'owner', title: 'Owner', render: (item) => item.owner },
            { key: 'action', title: 'Action', render: (item) => <button style={styles.buttonSecondary} onClick={() => startEdit(item)}>Edit</button> },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const data = await getPlaceholderResource('/client');
    return { props: { total: data.pagination?.total ?? data.items?.length ?? 0 } };
  } catch (error) {
    return { props: { total: 0, error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
