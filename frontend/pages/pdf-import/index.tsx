import { useEffect, useRef, useState } from 'react';
import Layout from '../../components/Layout';
import { useToast } from '../../components/Toast';
import {
  Account,
  PdfImportBatchRecord,
  ValidationResult,
  getAccounts,
  uploadPdfBatch,
  getPdfBatch,
  confirmPdfBatch,
  resetPdfBatch,
  listPdfBatches,
} from '../../lib/api';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, styles } from '../../lib/ui';

type Props = { accounts: Account[]; batches: PdfImportBatchRecord[]; error?: string };

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

  // per-position editable state: asset_code → { selected, average_cost }
  const [posEdits, setPosEdits] = useState<Record<string, { selected: boolean; average_cost: string }>>({});

  const parsed = activeBatch?.parsed_data ?? {};
  const positions: any[] = parsed.positions ?? [];
  const cashBalances: any[] = parsed.cash_balances ?? [];
  const capitalEvents: any[] = parsed.capital_events ?? [];
  const trades: any[] = parsed.trades ?? [];
  const confidence: string = parsed.parsing_confidence ?? '';
  const validation: ValidationResult | null | undefined = activeBatch?.validation ?? parsed._validation ?? null;

  // initialise edits whenever active batch changes
  useEffect(() => {
    if (!activeBatch) return;
    const init: Record<string, { selected: boolean; average_cost: string }> = {};
    (activeBatch.parsed_data?.positions ?? []).forEach((p: any) => {
      const key = p.asset_code;
      init[key] = { selected: true, average_cost: String(p.average_cost ?? '') };
    });
    setPosEdits(init);
  }, [activeBatch?.id]);

  // Poll parsing batch
  useEffect(() => {
    if (activeBatch?.status === 'parsing') {
      pollRef.current = setInterval(async () => {
        try {
          const updated = await getPdfBatch(activeBatch.id);
          setActiveBatch(updated);
          setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
          if (updated.status !== 'parsing' && pollRef.current) clearInterval(pollRef.current);
        } catch { if (pollRef.current) clearInterval(pollRef.current); }
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
    } catch (err) { showToast(err instanceof Error ? err.message : '上传失败', 'error'); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; }
  }

  async function handleConfirm() {
    if (!activeBatch) return;
    const selectedPositions = positions
      .filter((p) => posEdits[p.asset_code]?.selected !== false)
      .map((p) => ({
        ...p,
        average_cost: posEdits[p.asset_code]?.average_cost !== ''
          ? Number(posEdits[p.asset_code]?.average_cost) || p.average_cost
          : p.average_cost,
      }));

    const confirmedData = {
      ...(activeBatch.parsed_data ?? {}),
      positions: selectedPositions,
    };

    setConfirming(true);
    try {
      const updated = await confirmPdfBatch(activeBatch.id, confirmedData);
      setActiveBatch(updated);
      setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      showToast(`${selectedPositions.length} 项持仓已写入数据库`, 'success');
    } catch (err) { showToast(err instanceof Error ? err.message : '确认失败', 'error'); }
    finally { setConfirming(false); }
  }

  async function handleReset(batchId: number) {
    try {
      const updated = await resetPdfBatch(batchId);
      setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      if (activeBatch?.id === batchId) setActiveBatch(updated);
      showToast('已重置', 'success');
    } catch (err) { showToast(err instanceof Error ? err.message : '重置失败', 'error'); }
  }

  function toggleAll(val: boolean) {
    setPosEdits((prev) => {
      const next = { ...prev };
      positions.forEach((p) => { if (next[p.asset_code]) next[p.asset_code] = { ...next[p.asset_code], selected: val }; });
      return next;
    });
  }

  const selectedCount = positions.filter((p) => posEdits[p.asset_code]?.selected !== false).length;

  // Validation level per asset_code
  const validationMap: Record<string, 'error' | 'warning'> = {};
  (validation?.errors ?? []).forEach((e) => { validationMap[e.asset_code] = 'error'; });
  (validation?.warnings ?? []).forEach((w) => { if (!validationMap[w.asset_code]) validationMap[w.asset_code] = 'warning'; });

  return (
    <Layout title='PDF 年度账单导入' subtitle='上传券商年度 PDF 账单，AI 解析后人工确认写入' requiredPermission='import.write'>
      {error && <div style={{ ...styles.card, color: colors.danger, marginBottom: 16 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {/* ── Upload + history panel ── */}
        <div style={{ ...styles.card, flex: '0 0 300px' }}>
          <h3 style={{ marginTop: 0 }}>上传年度账单</h3>
          <form onSubmit={handleUpload} style={{ display: 'grid', gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>账户</div>
              <select style={styles.input} value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
                <option value=''>请选择账户…</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.broker} · {a.account_no}</option>)}
              </select>
            </div>
            <div>
              <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>年末快照日期</div>
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
              <div key={b.id} onClick={() => setActiveBatch(b)} style={{
                padding: '8px 12px', marginBottom: 6, borderRadius: 6, cursor: 'pointer',
                background: activeBatch?.id === b.id ? '#eff6ff' : '#f8fafc',
                border: `1px solid ${activeBatch?.id === b.id ? colors.primary : colors.border}`,
              }}>
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

        {/* ── Preview panel ── */}
        {activeBatch && (
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Header */}
            <div style={{ ...styles.card, marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <h3 style={{ margin: 0 }}>
                  解析结果 — {activeBatch.snapshot_date}
                  {activeBatch.ai_model && <span style={{ fontSize: 12, color: colors.muted, marginLeft: 8 }}>({activeBatch.ai_model})</span>}
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  {activeBatch.status === 'parsed' && positions.length > 0 && (
                    <button style={styles.buttonPrimary} onClick={handleConfirm} disabled={confirming || selectedCount === 0}>
                      {confirming ? '写入中…' : `确认写入 ${selectedCount} 项持仓`}
                    </button>
                  )}
                  {['parsed', 'confirmed', 'failed', 'confirmed_pending_deposits'].includes(activeBatch.status) && (
                    <button style={{ ...styles.buttonSecondary, color: colors.danger }} onClick={() => handleReset(activeBatch.id)}>重置</button>
                  )}
                </div>
              </div>

              {activeBatch.status === 'parsing' && (
                <div style={{ padding: '20px', textAlign: 'center', color: colors.muted }}>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
                  AI 解析中，请稍候…
                </div>
              )}
              {activeBatch.status === 'failed' && (
                <div style={{ color: colors.danger, fontSize: 13, marginTop: 8 }}>
                  <strong>解析失败：</strong>{activeBatch.failed_reason}
                </div>
              )}
              {confidence && confidence !== 'high' && activeBatch.status === 'parsed' && (
                <div style={{ background: '#fff7ed', border: '1px solid #fb923c', borderRadius: 6, padding: '8px 12px', marginTop: 10, fontSize: 13 }}>
                  ⚠️ 解析置信度: <strong>{confidence}</strong>，请仔细核对后再确认写入
                </div>
              )}
            </div>

            {/* Validation summary */}
            {validation && activeBatch.status === 'parsed' && (validation.errors.length > 0 || validation.warnings.length > 0) && (
              <div style={{ ...styles.card, marginBottom: 16, fontSize: 13 }}>
                <strong>置信度校验</strong>
                {validation.errors.length > 0 && (
                  <span style={{ marginLeft: 12, color: '#dc2626' }}>🔴 {validation.errors.length} 项差异 &gt;20%</span>
                )}
                {validation.warnings.length > 0 && (
                  <span style={{ marginLeft: 12, color: '#d97706' }}>⚠️ {validation.warnings.length} 项差异 5-20%</span>
                )}
                <span style={{ marginLeft: 12, color: colors.muted }}>— 可勾选跳过问题项，单独确认其余持仓</span>
              </div>
            )}

            {/* Positions table with checkboxes + inline avg cost edit */}
            {positions.length > 0 && activeBatch.status === 'parsed' && (
              <div style={{ ...styles.card, marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <h4 style={{ margin: 0 }}>持仓 ({positions.length} 项，已选 {selectedCount} 项)</h4>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button style={{ ...styles.buttonSecondary, fontSize: 12, padding: '3px 10px' }} onClick={() => toggleAll(true)}>全选</button>
                    <button style={{ ...styles.buttonSecondary, fontSize: 12, padding: '3px 10px' }} onClick={() => toggleAll(false)}>全不选</button>
                  </div>
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', borderBottom: `1px solid ${colors.border}` }}>
                        <th style={{ padding: '6px 8px', textAlign: 'left', width: 32 }}></th>
                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>代码</th>
                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>名称</th>
                        <th style={{ padding: '6px 8px', textAlign: 'right' }}>数量</th>
                        <th style={{ padding: '6px 8px', textAlign: 'right' }}>均价（可编辑）</th>
                        <th style={{ padding: '6px 8px', textAlign: 'right' }}>市值</th>
                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>币种</th>
                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>类型</th>
                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>校验</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((p) => {
                        const key = p.asset_code;
                        const edit = posEdits[key] ?? { selected: true, average_cost: String(p.average_cost ?? '') };
                        const vLevel = validationMap[key];
                        const rowBg = !edit.selected ? '#f8fafc' : vLevel === 'error' ? '#fff8f8' : vLevel === 'warning' ? '#fffdf0' : 'white';
                        return (
                          <tr key={key} style={{ borderBottom: `1px solid ${colors.border}`, background: rowBg, opacity: edit.selected ? 1 : 0.45 }}>
                            <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                              <input type='checkbox' checked={edit.selected}
                                onChange={(e) => setPosEdits((prev) => ({ ...prev, [key]: { ...prev[key], selected: e.target.checked } }))} />
                            </td>
                            <td style={{ padding: '6px 8px' }}><strong>{p.asset_code}</strong></td>
                            <td style={{ padding: '6px 8px', color: colors.muted }}>{p.asset_name || '—'}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right' }}>{p.quantity}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                              <input
                                type='number'
                                step='any'
                                value={edit.average_cost}
                                onChange={(e) => setPosEdits((prev) => ({ ...prev, [key]: { ...prev[key], average_cost: e.target.value } }))}
                                style={{
                                  width: 90, textAlign: 'right', border: `1px solid ${colors.border}`,
                                  borderRadius: 4, padding: '2px 4px', fontSize: 13,
                                  background: edit.average_cost !== String(p.average_cost ?? '') ? '#fffbeb' : 'white',
                                }}
                              />
                              {p.average_cost_from_trades && (
                                <div style={{ fontSize: 11, color: '#2563eb', marginTop: 2, cursor: 'pointer' }}
                                  title='点击使用交易记录计算的均价'
                                  onClick={() => setPosEdits((prev) => ({ ...prev, [key]: { ...prev[key], average_cost: String(p.average_cost_from_trades) } }))}>
                                  📊 交易均价: {p.average_cost_from_trades}
                                </div>
                              )}
                            </td>
                            <td style={{ padding: '6px 8px', textAlign: 'right' }}>{p.market_value ?? '—'}</td>
                            <td style={{ padding: '6px 8px' }}>{p.currency}</td>
                            <td style={{ padding: '6px 8px', color: colors.muted }}>{p.asset_type || '—'}</td>
                            <td style={{ padding: '6px 8px' }}>
                              {vLevel === 'error' && <span style={{ color: '#dc2626', fontWeight: 600 }}>🔴 差异大</span>}
                              {vLevel === 'warning' && <span style={{ color: '#d97706' }}>⚠️ 差异</span>}
                              {!vLevel && <span style={{ color: '#16a34a' }}>✅</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Positions view-only (confirmed) */}
            {positions.length > 0 && activeBatch.status !== 'parsed' && (
              <div style={{ ...styles.card, marginBottom: 16 }}>
                <h4 style={{ marginTop: 0 }}>持仓 ({positions.length})</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', borderBottom: `1px solid ${colors.border}` }}>
                        {['代码','名称','数量','均价','市值','币种','类型'].map((h) => (
                          <th key={h} style={{ padding: '6px 8px', textAlign: 'left' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((p) => (
                        <tr key={p.asset_code} style={{ borderBottom: `1px solid ${colors.border}` }}>
                          <td style={{ padding: '6px 8px' }}><strong>{p.asset_code}</strong></td>
                          <td style={{ padding: '6px 8px', color: colors.muted }}>{p.asset_name || '—'}</td>
                          <td style={{ padding: '6px 8px' }}>{p.quantity}</td>
                          <td style={{ padding: '6px 8px' }}>{p.average_cost ?? '—'}</td>
                          <td style={{ padding: '6px 8px' }}>{p.market_value ?? '—'}</td>
                          <td style={{ padding: '6px 8px' }}>{p.currency}</td>
                          <td style={{ padding: '6px 8px', color: colors.muted }}>{p.asset_type || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Cash balances */}
            {cashBalances.length > 0 && (
              <div style={{ ...styles.card, marginBottom: 16 }}>
                <h4 style={{ marginTop: 0 }}>现金余额</h4>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead><tr style={{ background: '#f8fafc' }}>
                    <th style={{ padding: '6px 8px', textAlign: 'left' }}>币种</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>余额</th>
                  </tr></thead>
                  <tbody>{cashBalances.map((c, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
                      <td style={{ padding: '6px 8px' }}>{c.currency}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>{c.balance}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}

            {/* Trades */}
            {trades.length > 0 && (
              <div style={{ ...styles.card, marginBottom: 16 }}>
                <h4 style={{ marginTop: 0 }}>交易记录 ({trades.length} 笔)</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead><tr style={{ background: '#f8fafc', borderBottom: `1px solid ${colors.border}` }}>
                      {['日期','代码','方向','数量','价格','币种','手续费'].map((h) => (
                        <th key={h} style={{ padding: '5px 8px', textAlign: 'left' }}>{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>{trades.map((t, i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
                        <td style={{ padding: '5px 8px' }}>{t.date || '—'}</td>
                        <td style={{ padding: '5px 8px' }}><strong>{t.asset_code}</strong></td>
                        <td style={{ padding: '5px 8px', color: t.side === 'buy' ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
                          {t.side === 'buy' ? '买入' : t.side === 'sell' ? '卖出' : t.side || '—'}
                        </td>
                        <td style={{ padding: '5px 8px' }}>{t.quantity}</td>
                        <td style={{ padding: '5px 8px' }}>{t.price}</td>
                        <td style={{ padding: '5px 8px' }}>{t.currency || '—'}</td>
                        <td style={{ padding: '5px 8px', color: colors.muted }}>{t.commission ?? '—'}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Capital events */}
            {capitalEvents.length > 0 && (
              <div style={styles.card}>
                <h4 style={{ marginTop: 0 }}>资本事件</h4>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead><tr style={{ background: '#f8fafc' }}>
                    {['日期','类型','金额','备注'].map((h) => <th key={h} style={{ padding: '6px 8px', textAlign: 'left' }}>{h}</th>)}
                  </tr></thead>
                  <tbody>{capitalEvents.map((e, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
                      <td style={{ padding: '6px 8px' }}>{e.date}</td>
                      <td style={{ padding: '6px 8px' }}>{e.type}</td>
                      <td style={{ padding: '6px 8px' }}>{e.amount} {e.currency}</td>
                      <td style={{ padding: '6px 8px', color: colors.muted }}>{e.note || '—'}</td>
                    </tr>
                  ))}</tbody>
                </table>
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
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, accounts: [], batches: [], error: error?.message || 'Failed to load.' },
    };
  }
}
