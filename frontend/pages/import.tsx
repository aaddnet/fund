import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { getPlaceholderResource } from '../lib/api';
import { styles } from '../lib/ui';

type ImportDraft = {
  id: number;
  source: string;
  filename: string;
  status: string;
  note: string;
};

type Props = {
  total: number;
  error?: string;
};

export default function Page({ total, error }: Props) {
  const [rows, setRows] = useState<ImportDraft[]>([
    { id: 1, source: 'IB', filename: 'ib-2026-03.csv', status: 'Ready', note: 'March statement parsed' },
    { id: 2, source: 'Kraken', filename: 'kraken-2026-06.csv', status: 'Needs mapping', note: 'Asset aliases pending' },
  ]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const current = useMemo(() => rows.find((item) => item.id === editingId), [rows, editingId]);
  const [form, setForm] = useState({ source: 'IB', filename: '', status: 'Draft', note: '' });

  function resetForm() {
    setEditingId(null);
    setForm({ source: 'IB', filename: '', status: 'Draft', note: '' });
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

  function startEdit(row: ImportDraft) {
    setEditingId(row.id);
    setForm({ source: row.source, filename: row.filename, status: row.status, note: row.note });
  }

  return (
    <Layout title='Import Batches' subtitle='Manage statement ingestion drafts with a cleaner operational review interface.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{editingId ? 'Edit Import Draft' : 'Create Import Draft'}</h3>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14 }}>
            <FormField label='Source'><input style={styles.input} value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} /></FormField>
            <FormField label='Filename'><input style={styles.input} value={form.filename} onChange={(e) => setForm({ ...form, filename: e.target.value })} /></FormField>
            <FormField label='Status'><input style={styles.input} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} /></FormField>
            <FormField label='Ops Note'><textarea style={{ ...styles.input, minHeight: 90 }} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></FormField>
            <div style={{ display: 'flex', gap: 10 }}>
              <button style={styles.buttonPrimary} type='submit'>{editingId ? 'Save Changes' : 'Create Draft'}</button>
              <button style={styles.buttonSecondary} type='button' onClick={resetForm}>Reset</button>
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Backend Status</h3>
          <p>Placeholder import endpoint total: {total}</p>
          <p style={{ color: '#64748b' }}>This form gives you a product-grade review flow now, while import write APIs are still placeholders on the backend.</p>
          {current ? <p style={{ marginBottom: 0 }}>Editing: {current.filename}</p> : null}
        </div>
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Import Draft Queue</h3>
        <ProductTable
          emptyText='No import drafts yet.'
          rows={rows}
          columns={[
            { key: 'source', title: 'Source', render: (item) => item.source },
            { key: 'file', title: 'Filename', render: (item) => item.filename },
            { key: 'status', title: 'Status', render: (item) => item.status },
            { key: 'note', title: 'Ops Note', render: (item) => item.note },
            { key: 'action', title: 'Action', render: (item) => <button style={styles.buttonSecondary} onClick={() => startEdit(item)}>Edit</button> },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const data = await getPlaceholderResource('/import');
    return { props: { total: data.pagination?.total ?? data.items?.length ?? 0 } };
  } catch (error) {
    return { props: { total: 0, error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
