import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { confirmImportBatch, getImportBatches, ImportBatch, uploadImportBatch } from '../lib/api';
import { colors, styles } from '../lib/ui';

type Props = {
  batches: ImportBatch[];
  error?: string;
};

const statusColorMap: Record<string, string> = {
  uploaded: colors.warning,
  parsed: colors.primary,
  confirmed: colors.success,
  failed: colors.danger,
};

export default function Page({ batches, error }: Props) {
  const [rows, setRows] = useState<ImportBatch[]>(batches);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(batches[0]?.id ?? null);
  const [source, setSource] = useState('csv');
  const [accountId, setAccountId] = useState('1');
  const [file, setFile] = useState<File | null>(null);
  const [submitState, setSubmitState] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const selectedBatch = useMemo(() => rows.find((item) => item.id === selectedBatchId) ?? rows[0] ?? null, [rows, selectedBatchId]);

  function mergeBatch(batch: ImportBatch) {
    setRows((current) => {
      const merged = [batch, ...current.filter((item) => item.id !== batch.id)];
      return merged.sort((left, right) => right.id - left.id);
    });
    setSelectedBatchId(batch.id);
  }

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setSubmitState('Please choose a CSV file first.');
      return;
    }

    setSubmitting(true);
    setSubmitState('');
    try {
      const batch = await uploadImportBatch({ source, accountId: Number(accountId), file });
      mergeBatch(batch);
      setSubmitState(batch.status === 'failed' ? batch.failed_reason || 'Import parsing failed.' : `Uploaded ${batch.filename} with ${batch.parsed_count} parsed rows.`);
      setFile(null);
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : 'Failed to upload CSV.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm(batchId: number) {
    setSubmitting(true);
    setSubmitState('');
    try {
      const confirmed = await confirmImportBatch(batchId);
      mergeBatch(confirmed);
      setSubmitState(`Confirmed batch #${confirmed.id}. Transactions and positions were created.`);
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : 'Failed to confirm import batch.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title='Import Batches' subtitle='Upload CSV statements, preview parsed rows, and confirm a minimal real import flow.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Upload CSV</h3>
          <form onSubmit={handleUpload} style={{ display: 'grid', gap: 14 }}>
            <FormField label='Source'>
              <input style={styles.input} value={source} onChange={(event) => setSource(event.target.value)} />
            </FormField>
            <FormField label='Account ID'>
              <input style={styles.input} value={accountId} onChange={(event) => setAccountId(event.target.value)} />
            </FormField>
            <FormField label='CSV File'>
              <input style={styles.input} type='file' accept='.csv,text/csv' onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </FormField>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
                {submitting ? 'Uploading...' : 'Upload & Parse'}
              </button>
              {submitState ? <span style={{ color: submitState.toLowerCase().includes('failed') || submitState.toLowerCase().includes('error') ? colors.danger : colors.success }}>{submitState}</span> : null}
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>CSV Format</h3>
          <p style={{ marginTop: 0, color: colors.muted }}>Required columns:</p>
          <code>trade_date, asset_code, quantity, price, currency, tx_type</code>
          <p style={{ color: colors.muted }}>Optional columns: fee, snapshot_date</p>
          <p style={{ marginBottom: 0, color: colors.muted }}>Confirm will write transactions and rebuild positions per snapshot date for the selected account.</p>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Batch Queue</h3>
        <ProductTable
          emptyText='No import batches yet.'
          rows={rows}
          columns={[
            { key: 'id', title: 'Batch', render: (item) => `#${item.id}` },
            { key: 'source', title: 'Source', render: (item) => item.source },
            { key: 'filename', title: 'Filename', render: (item) => item.filename },
            { key: 'account', title: 'Account', render: (item) => item.account_id },
            { key: 'status', title: 'Status', render: (item) => <span style={{ ...styles.chip, color: statusColorMap[item.status] || colors.primary }}>{item.status}</span> },
            { key: 'rows', title: 'Rows', render: (item) => `${item.parsed_count}/${item.row_count}` },
            {
              key: 'actions',
              title: 'Actions',
              render: (item) => (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button style={styles.buttonSecondary} onClick={() => setSelectedBatchId(item.id)}>Preview</button>
                  <button style={styles.buttonPrimary} disabled={submitting || item.status !== 'parsed'} onClick={() => handleConfirm(item.id)}>
                    Confirm
                  </button>
                </div>
              ),
            },
          ]}
        />
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Batch Preview</h3>
        {!selectedBatch ? <p style={{ color: colors.muted }}>Select or upload a batch to inspect parsed rows.</p> : null}
        {selectedBatch ? (
          <>
            <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
              <div><strong>Batch:</strong> #{selectedBatch.id} / {selectedBatch.filename}</div>
              <div><strong>Status:</strong> {selectedBatch.status}</div>
              <div><strong>Failed reason:</strong> {selectedBatch.failed_reason || '—'}</div>
            </div>
            <ProductTable
              emptyText='No preview rows available.'
              rows={selectedBatch.preview_rows}
              columns={[
                { key: 'row', title: 'Row', render: (item) => item.row_number },
                { key: 'date', title: 'Trade Date', render: (item) => item.trade_date },
                { key: 'asset', title: 'Asset', render: (item) => item.asset_code },
                { key: 'qty', title: 'Quantity', render: (item) => item.quantity },
                { key: 'price', title: 'Price', render: (item) => item.price },
                { key: 'currency', title: 'Currency', render: (item) => item.currency },
                { key: 'type', title: 'Type', render: (item) => item.tx_type },
                { key: 'snapshot', title: 'Snapshot Date', render: (item) => item.snapshot_date },
              ]}
            />
          </>
        ) : null}
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    return { props: { batches: await getImportBatches() } };
  } catch (error) {
    return { props: { batches: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
