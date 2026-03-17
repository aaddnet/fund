import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { confirmImportBatch, getImportBatches, ImportBatch, uploadImportBatch } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
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
  const { hasPermission } = useAuth();
  const { t } = useI18n();
  const canWriteImport = hasPermission('import.write');
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
    if (!canWriteImport) {
      setSubmitState(t('permissionDenied'));
      return;
    }
    if (!file) {
      setSubmitState(t('chooseCsvFirst'));
      return;
    }

    setSubmitting(true);
    setSubmitState('');
    try {
      const batch = await uploadImportBatch({ source, accountId: Number(accountId), file });
      mergeBatch(batch);
      setSubmitState(batch.status === 'failed' ? batch.failed_reason || t('importParsingFailed') : t('importUploaded', { filename: batch.filename, count: batch.parsed_count }));
      setFile(null);
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : t('importParsingFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm(batchId: number) {
    if (!canWriteImport) {
      setSubmitState(t('permissionDenied'));
      return;
    }
    setSubmitting(true);
    setSubmitState('');
    try {
      const confirmed = await confirmImportBatch(batchId);
      mergeBatch(confirmed);
      setSubmitState(t('confirmSuccess', { batchId: confirmed.id }));
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : t('permissionDenied'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title={t('importTitle')} subtitle={t('importSubtitle')} requiredPermission='import.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>{t('backendWarning')}: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('uploadCsv')}</h3>
          <form onSubmit={handleUpload} style={{ display: 'grid', gap: 14 }}>
            <FormField label={t('source')}>
              <input style={styles.input} value={source} onChange={(event) => setSource(event.target.value)} disabled={!canWriteImport} />
            </FormField>
            <FormField label={t('accountId')}>
              <input style={styles.input} value={accountId} onChange={(event) => setAccountId(event.target.value)} disabled={!canWriteImport} />
            </FormField>
            <FormField label={t('csvFile')}>
              <input style={styles.input} type='file' accept='.csv,text/csv' onChange={(event) => setFile(event.target.files?.[0] ?? null)} disabled={!canWriteImport} />
            </FormField>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <button style={styles.buttonPrimary} disabled={submitting || !canWriteImport} type='submit'>
                {submitting ? t('uploading') : t('uploadAndParse')}
              </button>
              {!canWriteImport ? <span style={{ color: colors.warning }}>{t('readOnlyView')}</span> : null}
              {submitState ? <span style={{ color: submitState.toLowerCase().includes('failed') || submitState.toLowerCase().includes('error') || submitState.includes('失败') ? colors.danger : colors.success }}>{submitState}</span> : null}
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('csvFormat')}</h3>
          <p style={{ marginTop: 0, color: colors.muted }}>{t('requiredColumns')}</p>
          <code>trade_date, asset_code, quantity, price, currency, tx_type</code>
          <p style={{ color: colors.muted }}>{t('optionalColumns')}</p>
          <p style={{ marginBottom: 0, color: colors.muted }}>{t('confirmHint')}</p>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('batchQueue')}</h3>
        <ProductTable
          emptyText={t('noImportBatches')}
          rows={rows}
          columns={[
            { key: 'id', title: t('batch'), render: (item) => `#${item.id}` },
            { key: 'source', title: t('source'), render: (item) => item.source },
            { key: 'filename', title: t('filename'), render: (item) => item.filename },
            { key: 'account', title: t('accountId'), render: (item) => item.account_id },
            { key: 'status', title: t('status'), render: (item) => <span style={{ ...styles.chip, color: statusColorMap[item.status] || colors.primary }}>{item.status}</span> },
            { key: 'rows', title: t('rows'), render: (item) => `${item.parsed_count}/${item.row_count}` },
            {
              key: 'actions',
              title: t('actions'),
              render: (item) => (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button style={styles.buttonSecondary} onClick={() => setSelectedBatchId(item.id)}>{t('preview')}</button>
                  <button style={styles.buttonPrimary} disabled={submitting || item.status !== 'parsed' || !canWriteImport} onClick={() => handleConfirm(item.id)}>
                    {t('confirm')}
                  </button>
                </div>
              ),
            },
          ]}
        />
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('batchPreview')}</h3>
        {!selectedBatch ? <p style={{ color: colors.muted }}>{t('selectBatch')}</p> : null}
        {selectedBatch ? (
          <>
            <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
              <div><strong>{t('batch')}:</strong> #{selectedBatch.id} / {selectedBatch.filename}</div>
              <div><strong>{t('status')}:</strong> {selectedBatch.status}</div>
              <div><strong>{t('failedReason')}:</strong> {selectedBatch.failed_reason || t('notAvailable')}</div>
            </div>
            <ProductTable
              emptyText={t('noImportBatches')}
              rows={selectedBatch.preview_rows}
              columns={[
                { key: 'row', title: t('row'), render: (item) => item.row_number },
                { key: 'date', title: 'Trade Date', render: (item) => item.trade_date },
                { key: 'asset', title: 'Asset', render: (item) => item.asset_code },
                { key: 'qty', title: t('quantity'), render: (item) => item.quantity },
                { key: 'price', title: t('price'), render: (item) => item.price },
                { key: 'currency', title: t('currency'), render: (item) => item.currency },
                { key: 'type', title: t('type'), render: (item) => item.tx_type },
                { key: 'snapshot', title: 'Snapshot Date', render: (item) => item.snapshot_date },
              ]}
            />
          </>
        ) : null}
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, batches: await getImportBatches(auth.accessToken) } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, batches: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
