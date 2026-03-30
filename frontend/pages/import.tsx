import { useEffect, useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import {
  Account, Client,
  confirmDeposit, confirmImportBatch, getAccounts, getClients, getImportBatches,
  ImportBatch, PendingDeposit, resetImportBatch, uploadImportBatch,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  batches: ImportBatch[];
  accounts: Account[];
  clients: Client[];
  error?: string;
};

const SOURCES = [
  { value: 'csv',    label: 'Generic CSV' },
  { value: 'moomoo', label: 'Moomoo / Futu' },
  { value: 'ib',     label: 'Interactive Brokers' },
  { value: 'schwab', label: 'Charles Schwab' },
  { value: 'kraken', label: 'Kraken' },
];

const statusColorMap: Record<string, string> = {
  uploaded: colors.warning,
  parsed: colors.primary,
  confirmed: colors.success,
  confirmed_pending_deposits: colors.warning,
  failed: colors.danger,
  reset: colors.muted,
};

export default function Page({ batches, accounts, clients, error }: Props) {
  const { hasPermission } = useAuth();
  const { t } = useI18n();
  const { showToast } = useToast();
  const canWriteImport = hasPermission('import.write');

  const [rows, setRows] = useState<ImportBatch[]>(batches);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(batches[0]?.id ?? null);
  const [activeTab, setActiveTab] = useState<'queue' | 'history'>('queue');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [source, setSource] = useState('csv');
  const [accountId, setAccountId] = useState(() => String(accounts[0]?.id ?? '1'));
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const selectedBatch = useMemo(() => rows.find((item) => item.id === selectedBatchId) ?? rows[0] ?? null, [rows, selectedBatchId]);

  // Deposit confirmation state
  const [depositSelections, setDepositSelections] = useState<Record<number, { confirmAs: string; clientId: string }>>({});

  // Filter accounts by selected source/broker (csv = show all)
  const filteredAccounts = useMemo(() => {
    if (source === 'csv') return accounts;
    return accounts.filter(a => a.broker === source);
  }, [accounts, source]);

  useEffect(() => {
    if (filteredAccounts.length > 0 && !filteredAccounts.find(a => String(a.id) === accountId)) {
      setAccountId(String(filteredAccounts[0].id));
    }
  }, [filteredAccounts]);

  // Reset deposit selections when selected batch changes
  useEffect(() => {
    setDepositSelections({});
  }, [selectedBatchId]);

  function mergeBatch(batch: ImportBatch) {
    setRows((current) => {
      const merged = [batch, ...current.filter((item) => item.id !== batch.id)];
      return merged.sort((left, right) => right.id - left.id);
    });
    setSelectedBatchId(batch.id);
  }

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWriteImport) { showToast(t('permissionDenied'), 'error'); return; }
    if (!file) { showToast(t('chooseCsvFirst'), 'error'); return; }
    setSubmitting(true);
    try {
      const batch = await uploadImportBatch({ source, accountId: Number(accountId), file });
      mergeBatch(batch);
      if (batch.status === 'failed') {
        showToast(batch.failed_reason || t('importParsingFailed'), 'error');
      } else {
        showToast(t('importUploaded', { filename: batch.filename, count: batch.parsed_count }), 'success');
        setIsModalOpen(false);
        setFile(null);
      }
    } catch (submitError) {
      showToast(submitError instanceof Error ? submitError.message : t('importParsingFailed'), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm(batchId: number) {
    if (!canWriteImport) { showToast(t('permissionDenied'), 'error'); return; }
    setSubmitting(true);
    try {
      const confirmed = await confirmImportBatch(batchId);
      mergeBatch(confirmed);
      showToast(t('confirmSuccess', { batchId: confirmed.id }), 'success');
    } catch (submitError) {
      showToast(submitError instanceof Error ? submitError.message : t('permissionDenied'), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReset(batchId: number) {
    if (!canWriteImport) { showToast(t('permissionDenied'), 'error'); return; }
    if (!confirm('Reset this batch? All transactions from this import will be deleted.')) return;
    setSubmitting(true);
    try {
      const batch = await resetImportBatch(batchId);
      mergeBatch(batch);
      showToast(`Batch #${batchId} has been reset.`, 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Reset failed.', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmAllDeposits(batch: ImportBatch) {
    if (!canWriteImport) { showToast(t('permissionDenied'), 'error'); return; }
    const deposits = batch.pending_deposits ?? [];
    const unhandled = deposits.filter((_, i) => !depositSelections[i]?.confirmAs);
    if (unhandled.length > 0) {
      showToast('Please select an action for all deposit records first.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      let latestBatch = batch;
      for (let i = 0; i < deposits.length; i++) {
        if (deposits[i].confirmed_as) continue; // already handled
        const sel = depositSelections[i];
        latestBatch = await confirmDeposit(batch.id, {
          deposit_index: i,
          client_id: sel.clientId ? Number(sel.clientId) : undefined,
          confirm_as: sel.confirmAs,
        });
      }
      mergeBatch(latestBatch);
      showToast('All deposit records confirmed.', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Deposit confirmation failed.', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  const pendingDeposits = selectedBatch?.pending_deposits ?? [];
  const hasPendingDeposits = pendingDeposits.length > 0 && pendingDeposits.some(d => !d.confirmed_as);
  const allDepositsSelected = pendingDeposits.every((_, i) => depositSelections[i]?.confirmAs || pendingDeposits[i]?.confirmed_as);

  return (
    <Layout title={t('importTitle')} subtitle={t('importSubtitle')} requiredPermission='import.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>{t('backendWarning')}: {error}</div> : null}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['queue', 'history'] as const).map(tab => (
            <button
              key={tab}
              style={{ ...styles.buttonSecondary, ...(activeTab === tab ? { background: colors.primary, color: '#fff', borderColor: colors.primary } : {}) }}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'queue' ? 'Import Queue' : 'Batch History'}
            </button>
          ))}
        </div>
        {canWriteImport && (
          <button style={styles.buttonPrimary} onClick={() => setIsModalOpen(true)}>+ {t('uploadCsv')}</button>
        )}
      </div>

      {activeTab === 'queue' ? (
        <>
          <div style={styles.card}>
            <h3 style={{ marginTop: 0 }}>{t('csvFormat')}</h3>
            <p style={{ marginTop: 0, color: colors.muted }}>{t('requiredColumns')}</p>
            <code>trade_date, asset_code, quantity, price, currency, tx_type</code>
            <p style={{ color: colors.muted }}>{t('optionalColumns')}</p>
            <p style={{ marginBottom: 0, color: colors.muted }}>{t('confirmHint')}</p>
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
                  <div><strong>{t('status')}:</strong> <span style={{ color: statusColorMap[selectedBatch.status] || colors.primary }}>{selectedBatch.status}</span></div>
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
                    { key: 'type', title: t('type'), render: (item) => <span style={{ color: item.tx_type === 'deposit_pending' ? colors.warning : undefined }}>{item.tx_type}</span> },
                    { key: 'snapshot', title: 'Snapshot Date', render: (item) => item.snapshot_date },
                  ]}
                />
              </>
            ) : null}
          </div>

          {/* Pending deposit confirmation section */}
          {selectedBatch && hasPendingDeposits && (
            <div style={{ ...styles.card, marginTop: 16, border: `2px solid ${colors.warning}` }}>
              <h3 style={{ marginTop: 0, color: colors.warning }}>⚠️ 发现存款记录，请确认处理方式</h3>
              <p style={{ color: colors.muted, marginTop: 0 }}>以下存款记录需要您决定是否创建为追加投资（additional）</p>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#f9fafb' }}>
                    {['日期', '金额 (USD)', '说明', '归属投资人', '处理方式', '状态'].map(h => (
                      <th key={h} style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pendingDeposits.map((dep, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '8px 12px' }}>{dep.date}</td>
                      <td style={{ padding: '8px 12px', fontWeight: 600 }}>${dep.amount_usd.toLocaleString()}</td>
                      <td style={{ padding: '8px 12px', color: colors.muted }}>{dep.note || dep.tx_type}</td>
                      <td style={{ padding: '8px 12px' }}>
                        {dep.confirmed_as ? '—' : (
                          <select
                            style={{ ...styles.input, padding: '4px 8px', fontSize: 12 }}
                            value={depositSelections[i]?.clientId ?? ''}
                            onChange={e => setDepositSelections(prev => ({ ...prev, [i]: { ...prev[i], clientId: e.target.value } }))}
                            disabled={submitting}
                          >
                            <option value="">— 选择投资人 —</option>
                            {clients.map(c => <option key={c.id} value={c.id}>#{c.id} · {c.name}</option>)}
                          </select>
                        )}
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        {dep.confirmed_as ? (
                          <span style={{ color: dep.confirmed_as === 'additional' ? colors.success : colors.muted }}>
                            {dep.confirmed_as === 'additional' ? '✅ 追加投资' : '⏭ 已跳过'}
                          </span>
                        ) : (
                          <div style={{ display: 'flex', gap: 6 }}>
                            <label style={{ cursor: 'pointer', fontSize: 12 }}>
                              <input type="radio" name={`dep_${i}`} value="additional"
                                checked={depositSelections[i]?.confirmAs === 'additional'}
                                onChange={() => setDepositSelections(prev => ({ ...prev, [i]: { ...prev[i], confirmAs: 'additional' } }))}
                              /> ✅ 追加投资
                            </label>
                            <label style={{ cursor: 'pointer', fontSize: 12 }}>
                              <input type="radio" name={`dep_${i}`} value="skip"
                                checked={depositSelections[i]?.confirmAs === 'skip'}
                                onChange={() => setDepositSelections(prev => ({ ...prev, [i]: { ...prev[i], confirmAs: 'skip' } }))}
                              /> ⏭ 跳过
                            </label>
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '8px 12px', color: dep.confirmed_as ? colors.success : colors.muted }}>
                        {dep.confirmed_as ? '已处理' : '待处理'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  style={{ ...styles.buttonPrimary, opacity: (!allDepositsSelected || submitting) ? 0.5 : 1 }}
                  disabled={!allDepositsSelected || submitting || !canWriteImport}
                  onClick={() => handleConfirmAllDeposits(selectedBatch)}
                >
                  {submitting ? '处理中...' : '确认所有存款处理'}
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        // History tab — batch management
        <div style={{ ...styles.card, marginTop: 0 }}>
          <h3 style={{ marginTop: 0 }}>历史批次管理</h3>
          <p style={{ color: colors.muted, marginTop: 0 }}>重置批次将删除该批次产生的所有交易记录（不删除持仓快照），并将状态置为 reset，可重新上传。</p>
          <ProductTable
            emptyText={t('noImportBatches')}
            rows={rows}
            columns={[
              { key: 'id', title: t('batch'), render: (item) => `#${item.id}` },
              { key: 'source', title: t('source'), render: (item) => item.source },
              { key: 'filename', title: t('filename'), render: (item) => item.filename },
              { key: 'account', title: 'Account', render: (item) => item.account_id },
              { key: 'status', title: t('status'), render: (item) => <span style={{ ...styles.chip, color: statusColorMap[item.status] || colors.primary }}>{item.status}</span> },
              { key: 'confirmed', title: '已确认', render: (item) => item.confirmed_count },
              { key: 'imported_at', title: '导入时间', render: (item) => item.imported_at ? item.imported_at.slice(0, 10) : '—' },
              ...(canWriteImport ? [{
                key: 'reset',
                title: '',
                render: (item: ImportBatch) => (
                  <button
                    style={{ ...styles.buttonSecondary, padding: '4px 8px', fontSize: 12, color: colors.danger, borderColor: colors.danger }}
                    disabled={submitting || item.status === 'reset'}
                    onClick={() => handleReset(item.id)}
                  >
                    重置批次
                  </button>
                ),
              }] : []),
            ]}
          />
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={t('uploadCsv')}>
        <form onSubmit={handleUpload} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('source')}>
            <select style={styles.input} value={source} onChange={(event) => setSource(event.target.value)} disabled={submitting}>
              {SOURCES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </FormField>
          <FormField label={t('accountId')}>
            <select style={styles.input} value={accountId} onChange={(event) => setAccountId(event.target.value)} disabled={submitting}>
              {filteredAccounts.length === 0 && (
                <option value="">— No {source} accounts found —</option>
              )}
              {filteredAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  #{a.id} · {a.fund_name ?? `Fund ${a.fund_id}`} / {a.broker} ({a.account_no})
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t('csvFile')}>
            <input style={styles.input} type='file' accept='.csv' onChange={(event) => setFile(event.target.files?.[0] || null)} disabled={submitting} />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={() => setIsModalOpen(false)} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting || !file} type='submit'>
              {submitting ? t('uploading') : t('uploadAndParse')}
            </button>
          </div>
        </form>
      </Modal>

    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [batches, accountData, clientData] = await Promise.all([
      getImportBatches({ accessToken: auth.accessToken }),
      getAccounts({ size: 100, accessToken: auth.accessToken }),
      getClients({ size: 100, accessToken: auth.accessToken }),
    ]);
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, batches, accounts: accountData.items ?? [], clients: clientData.items ?? [] } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, batches: [], accounts: [], clients: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
