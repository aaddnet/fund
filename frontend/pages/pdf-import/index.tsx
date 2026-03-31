import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import Layout from '../../components/Layout';
import ProductTable from '../../components/ProductTable';
import { useToast } from '../../components/Toast';
import {
  Account,
  PdfImportBatchRecord,
  getAccounts,
  uploadPdfBatch,
  getPdfBatch,
  confirmPdfBatch,
  resetPdfBatch,
  listPdfBatches,
} from '../../lib/api';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, styles } from '../../lib/ui';

type Props = {
  accounts: Account[];
  batches: PdfImportBatchRecord[];
  error?: string;
};

export default function Page({ accounts, batches: initialBatches, error }: Props) {
  const { showToast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const [accountId, setAccountId] = useState(accounts[0]?.id ? String(accounts[0].id) : '');
  const [snapshotDate, setSnapshotDate] = useState('');
  const [uploading, setUploading] = useState(false);
  const [batches, setBatches] = useState<PdfImportBatchRecord[]>(initialBatches);
  const [activeBatch, setActiveBatch] = useState<PdfImportBatchRecord | null>(null);
  const [confirming, setConfirming] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll a "parsing" batch until it's done
  useEffect(() => {
    if (activeBatch?.status === 'parsing') {
      pollRef.current = setInterval(async () => {
        try {
          const updated = await getPdfBatch(activeBatch.id);
          setActiveBatch(updated);
          setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
          if (updated.status !== 'parsing') {
            if (pollRef.current) clearInterval(pollRef.current);
          }
        } catch {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [activeBatch?.id, activeBatch?.status]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !accountId || !snapshotDate) return;
    setUploading(true);
    try {
      const batch = await uploadPdfBatch({ accountId: Number(accountId), snapshotDate, file });
      setBatches((prev) => [batch, ...prev]);
      setActiveBatch(batch);
      showToast('已上传，AI 解析中…', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : '上传失败', 'error');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function handleConfirm() {
    if (!activeBatch) return;
    setConfirming(true);
    try {
      const updated = await confirmPdfBatch(activeBatch.id, activeBatch.confirmed_data ?? activeBatch.parsed_data);
      setActiveBatch(updated);
      setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      showToast('持仓已写入数据库', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : '确认失败', 'error');
    } finally {
      setConfirming(false);
    }
  }

  async function handleReset(batchId: number) {
    try {
      const updated = await resetPdfBatch(batchId);
      setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      if (activeBatch?.id === batchId) setActiveBatch(updated);
      showToast('已重置', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : '重置失败', 'error');
    }
  }

  const parsed = activeBatch?.parsed_data ?? {};
  const positions: any[] = parsed.positions ?? [];
  const cashBalances: any[] = parsed.cash_balances ?? [];
  const capitalEvents: any[] = parsed.capital_events ?? [];
  const confidence: string = parsed.parsing_confidence ?? '';

  return (
    <Layout title='PDF 年度账单导入' subtitle='上传券商年度 PDF 账单，AI 解析后人工确认写入' requiredPermission='import.write'>
      {error && <div style={{ ...styles.card, color: colors.danger, marginBottom: 16 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {/* Upload Panel */}
        <div style={{ ...styles.card, flex: '0 0 340px' }}>
          <h3 style={{ marginTop: 0 }}>上传年度账单</h3>
          <form onSubmit={handleUpload} style={{ display: 'grid', gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>账户</div>
              <select style={styles.input} value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
                <option value=''>请选择账户…</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.broker} · {a.account_no}</option>
                ))}
              </select>
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>年末快照日期（如 2023-12-31）</div>
              <input type='date' style={styles.input} value={snapshotDate} onChange={(e) => setSnapshotDate(e.target.value)} required />
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>PDF 文件</div>
              <input ref={fileRef} type='file' accept='.pdf' style={styles.input} required />
            </div>
            <button style={styles.buttonPrimary} type='submit' disabled={uploading}>
              {uploading ? '上传中…' : '上传并解析'}
            </button>
          </form>

          <div style={{ marginTop: 20 }}>
            <h4 style={{ marginBottom: 8 }}>历史批次</h4>
            {batches.map((b) => (
              <div
                key={b.id}
                onClick={() => setActiveBatch(b)}
                style={{
                  padding: '8px 12px', marginBottom: 6, borderRadius: 6, cursor: 'pointer',
                  background: activeBatch?.id === b.id ? '#eff6ff' : '#f8fafc',
                  border: `1px solid ${activeBatch?.id === b.id ? colors.primary : colors.border}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: 13 }}>{b.snapshot_date}</strong>
                  <span style={{
                    fontSize: 11, fontWeight: 600,
                    color: b.status === 'confirmed' ? '#16a34a' : b.status === 'failed' ? '#dc2626' : b.status === 'parsing' ? '#d97706' : colors.muted,
                  }}>{b.status}</span>
                </div>
                <div style={{ fontSize: 12, color: colors.muted }}>{b.filename}</div>
              </div>
            ))}
            {batches.length === 0 && <div style={{ fontSize: 13, color: colors.muted }}>暂无批次记录</div>}
          </div>
        </div>

        {/* Preview Panel */}
        {activeBatch && (
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ ...styles.card, marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>
                  解析结果 — {activeBatch.snapshot_date}
                  {activeBatch.ai_model && <span style={{ fontSize: 12, color: colors.muted, marginLeft: 8 }}>({activeBatch.ai_model})</span>}
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  {activeBatch.status === 'parsed' && (
                    <button style={styles.buttonPrimary} onClick={handleConfirm} disabled={confirming}>
                      {confirming ? '写入中…' : '确认写入数据库'}
                    </button>
                  )}
                  {['parsed', 'confirmed', 'failed', 'confirmed_pending_deposits'].includes(activeBatch.status) && (
                    <button style={{ ...styles.buttonSecondary, color: colors.danger }} onClick={() => handleReset(activeBatch.id)}>
                      重置
                    </button>
                  )}
                </div>
              </div>

              {activeBatch.status === 'parsing' && (
                <div style={{ padding: '20px', textAlign: 'center', color: colors.muted }}>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
                  AI 解析中，请稍候（约 60-90 秒）…
                </div>
              )}

              {activeBatch.status === 'failed' && (
                <div style={{ color: colors.danger, fontSize: 13 }}>
                  <strong>解析失败：</strong>{activeBatch.failed_reason}
                </div>
              )}

              {confidence && confidence !== 'high' && activeBatch.status === 'parsed' && (
                <div style={{ background: '#fff7ed', border: '1px solid #fb923c', borderRadius: 6, padding: '8px 12px', marginBottom: 12, fontSize: 13 }}>
                  ⚠️ 解析置信度: <strong>{confidence}</strong>，请仔细核对以下数据再确认写入
                </div>
              )}
            </div>

            {positions.length > 0 && (
              <div style={{ ...styles.card, marginBottom: 16 }}>
                <h4 style={{ marginTop: 0 }}>持仓 ({positions.length})</h4>
                <ProductTable
                  emptyText='无持仓数据'
                  rows={positions}
                  columns={[
                    { key: 'code', title: '代码', render: (r) => <strong>{r.asset_code}</strong> },
                    { key: 'name', title: '名称', render: (r) => r.asset_name || '—' },
                    { key: 'qty', title: '数量', render: (r) => r.quantity },
                    { key: 'cost', title: '均价', render: (r) => r.average_cost ?? '—' },
                    { key: 'mktval', title: '市值', render: (r) => r.market_value ?? '—' },
                    { key: 'cur', title: '币种', render: (r) => r.currency },
                    { key: 'type', title: '类型', render: (r) => r.asset_type || '—' },
                  ]}
                />
              </div>
            )}

            {cashBalances.length > 0 && (
              <div style={{ ...styles.card, marginBottom: 16 }}>
                <h4 style={{ marginTop: 0 }}>现金余额</h4>
                <ProductTable
                  emptyText='无现金数据'
                  rows={cashBalances}
                  columns={[
                    { key: 'cur', title: '币种', render: (r) => r.currency },
                    { key: 'bal', title: '余额', render: (r) => r.balance },
                  ]}
                />
              </div>
            )}

            {capitalEvents.length > 0 && (
              <div style={styles.card}>
                <h4 style={{ marginTop: 0 }}>资本事件（需手动确认）</h4>
                <ProductTable
                  emptyText='无资本事件'
                  rows={capitalEvents}
                  columns={[
                    { key: 'date', title: '日期', render: (r) => r.date },
                    { key: 'type', title: '类型', render: (r) => r.type },
                    { key: 'amt', title: '金额', render: (r) => `${r.amount} ${r.currency}` },
                    { key: 'note', title: '备注', render: (r) => r.note || '—' },
                  ]}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  try {
    const [accountsResult, batchesResult] = await Promise.allSettled([
      getAccounts({ size: 200, accessToken: auth.accessToken }),
      listPdfBatches({ accessToken: auth.accessToken }),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        accounts: accountsResult.status === 'fulfilled' ? (accountsResult.value?.items ?? []) : [],
        batches: batchesResult.status === 'fulfilled' ? (batchesResult.value?.items ?? []) : [],
      },
    };
  } catch (error: any) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        accounts: [],
        batches: [],
        error: error?.message || 'Failed to load.',
      },
    };
  }
}
