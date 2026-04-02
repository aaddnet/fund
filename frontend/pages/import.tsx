/**
 * /import — CSV Import (V4.3 redesign)
 *
 * 3-step flow:
 *   Step 1: Select account + format + upload file
 *   Step 2: Preview parsed rows in tabs (交易记录 / 资金往来 / 利息费用 / 待处理)
 *           Each row has an inline type-select and edit button
 *   Step 3: Summary confirmation → write to DB
 */
import { useState } from 'react';
import Layout from '../components/Layout';
import { Account, ImportBatch, getAccounts, getImportBatches, uploadImportBatch, confirmImportBatch } from '../lib/api';
import { useToast } from '../components/Toast';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';
import { useAuth } from '../lib/auth';

// Inline style helpers not in legacy styles
const S = {
  select: {
    padding: '8px 12px',
    borderRadius: 8,
    border: `1px solid ${colors.border}`,
    fontSize: 14,
    background: '#fff',
  } as React.CSSProperties,
  btn: {
    padding: '8px 16px',
    borderRadius: 8,
    border: `1px solid ${colors.border}`,
    background: colors.primary,
    color: '#fff',
    fontSize: 14,
    cursor: 'pointer',
    fontWeight: 600,
  } as React.CSSProperties,
};

import React from 'react';

// ── Types ─────────────────────────────────────────────────────────────────

type PreviewRow = {
  index: number;
  trade_date: string;
  tx_category: string;
  tx_type: string;
  asset_code?: string;
  asset_name?: string;
  quantity?: number;
  price?: number;
  currency: string;
  gross_amount?: number;
  commission?: number;
  transaction_fee?: number;
  other_fee?: number;
  description?: string;
  is_other?: boolean;
  selected: boolean;
};

type Props = {
  accounts: Account[];
  batches: ImportBatch[];
  error?: string;
};

// ── Constants ─────────────────────────────────────────────────────────────

const SOURCES = [
  { value: 'ib',   label: 'Interactive Brokers (自动识别)' },
  { value: 'futu', label: 'Futu / Moomoo' },
  { value: 'csv',  label: '通用 CSV' },
];

const TX_TYPE_OPTIONS: { value: string; label: string; category: string }[] = [
  { value: 'stock_buy',       label: '股票买入',  category: 'TRADE' },
  { value: 'stock_sell',      label: '股票卖出',  category: 'TRADE' },
  { value: 'option_buy',      label: '期权买入',  category: 'TRADE' },
  { value: 'option_sell',     label: '期权卖出',  category: 'TRADE' },
  { value: 'option_expire',   label: '期权到期',  category: 'TRADE' },
  { value: 'deposit_eft',     label: '存款入金',  category: 'CASH' },
  { value: 'deposit_transfer',label: '存款划转',  category: 'CASH' },
  { value: 'withdrawal',      label: '提款',      category: 'CASH' },
  { value: 'dividend',        label: '股息',      category: 'CASH' },
  { value: 'pil',             label: '代付股息',  category: 'CASH' },
  { value: 'dividend_fee',    label: '股息税费',  category: 'CASH' },
  { value: 'interest_debit',  label: '融资利息',  category: 'CASH' },
  { value: 'interest_credit', label: '利息收入',  category: 'CASH' },
  { value: 'adr_fee',         label: 'ADR费用',   category: 'CASH' },
  { value: 'other_fee',       label: '其他费用',  category: 'CASH' },
  { value: 'adjustment',      label: '调整',      category: 'CASH' },
  { value: 'fx_trade',        label: '换汇',      category: 'FX' },
  { value: '__skip__',        label: '⏭ 跳过',   category: 'OTHER' },
];

const CATEGORY_TAB_MAP: Record<string, string> = {
  TRADE: '交易记录',
  CASH_DEPOSIT: '资金往来',
  CASH_INTEREST: '利息费用',
  FX: '换汇',
  OTHER: '待处理',
};

const TABS = ['TRADE', 'CASH_DEPOSIT', 'CASH_INTEREST', 'FX', 'OTHER'];

const STATUS_COLORS: Record<string, string> = {
  uploaded: colors.warning,
  parsed: colors.primary,
  confirmed: colors.success,
  failed: colors.danger,
  reset: colors.muted,
};

function tabForRow(row: PreviewRow): string {
  if (row.is_other || row.tx_type === '__skip__') return 'OTHER';
  const cat = (row.tx_category || '').toUpperCase();
  if (cat === 'TRADE') return 'TRADE';
  if (cat === 'FX') return 'FX';
  const cashDeposit = new Set(['deposit_eft', 'deposit_transfer', 'withdrawal', 'dividend', 'pil', 'dividend_fee', 'adjustment']);
  if (cat === 'CASH') return cashDeposit.has(row.tx_type) ? 'CASH_DEPOSIT' : 'CASH_INTEREST';
  return 'OTHER';
}

function netAmount(row: PreviewRow): number {
  return (row.gross_amount || 0) + (row.commission || 0) + (row.transaction_fee || 0) + (row.other_fee || 0);
}

// ── Main component ────────────────────────────────────────────────────────

export default function ImportPage({ accounts, batches: initialBatches, error }: Props) {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canImport = hasPermission('import.write');

  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Step 1
  const [accountId, setAccountId] = useState<string>(String(accounts[0]?.id ?? ''));
  const [source, setSource] = useState<string>('ib');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Step 2
  const [batchId, setBatchId] = useState<number | null>(null);
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([]);
  const [activeTab, setActiveTab] = useState<string>('TRADE');
  const [editingRow, setEditingRow] = useState<PreviewRow | null>(null);

  // Step 3
  const [confirming, setConfirming] = useState(false);

  const [batches] = useState<ImportBatch[]>(initialBatches);

  // ── Step 1: Upload ──
  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !canImport) return;
    setUploading(true);
    try {
      const result = await uploadImportBatch({ accountId: Number(accountId), source, file });
      setBatchId(result.id);

      // Build preview rows from parsed_data if available (V4.3 backend)
      const parsed = (result as any).parsed_rows || (result as any).parsed_data?.rows || [];
      const rows: PreviewRow[] = parsed.map((r: any, idx: number) => ({
        index: idx,
        trade_date:      r.trade_date || '',
        tx_category:     r.tx_category || 'TRADE',
        tx_type:         r.tx_type || 'stock_buy',
        asset_code:      r.asset_code,
        asset_name:      r.asset_name,
        quantity:        r.quantity,
        price:           r.price,
        currency:        r.currency || 'USD',
        gross_amount:    r.gross_amount,
        commission:      r.commission,
        transaction_fee: r.transaction_fee,
        other_fee:       r.other_fee,
        description:     r.description,
        is_other:        r.is_other || false,
        selected:        !r.is_other,
      }));

      setPreviewRows(rows);
      setStep(rows.length > 0 ? 2 : 3);
      showToast('文件上传成功', 'success');
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : '上传失败', 'error');
    } finally {
      setUploading(false);
    }
  }

  function updateRowType(index: number, newType: string) {
    setPreviewRows(prev => prev.map(r => {
      if (r.index !== index) return r;
      const opt = TX_TYPE_OPTIONS.find(o => o.value === newType);
      return { ...r, tx_type: newType, tx_category: opt?.category || r.tx_category, selected: newType !== '__skip__', is_other: newType === '__skip__' };
    }));
  }

  function toggleRowSelected(index: number) {
    setPreviewRows(prev => prev.map(r => r.index === index ? { ...r, selected: !r.selected } : r));
  }

  function skipAllOther() {
    setPreviewRows(prev => prev.map(r => r.is_other ? { ...r, selected: false } : r));
    showToast('已跳过所有待处理行', 'success');
  }

  async function handleConfirm() {
    if (!batchId) return;
    setConfirming(true);
    try {
      await confirmImportBatch(batchId);
      showToast('导入成功', 'success');
      setStep(1);
      setFile(null);
      setPreviewRows([]);
      setBatchId(null);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : '确认失败', 'error');
    } finally {
      setConfirming(false);
    }
  }

  const tabCounts = TABS.reduce((acc, t) => {
    acc[t] = previewRows.filter(r => tabForRow(r) === t).length;
    return acc;
  }, {} as Record<string, number>);

  const visibleRows = previewRows.filter(r => tabForRow(r) === activeTab);
  const selectedCount = previewRows.filter(r => r.selected && r.tx_type !== '__skip__').length;

  const assetCodeSet = new Set(previewRows.filter(r => r.asset_code).map(r => r.asset_code!));
  const assetCodes = Array.from(assetCodeSet);
  const dates = previewRows.map(r => r.trade_date).filter(Boolean).sort();

  return (
    <Layout title="CSV 批量导入">
      {error && (
        <div style={{ padding: '12px 16px', background: '#fee2e2', color: '#991b1b', borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Step indicator */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 28, borderBottom: `1px solid ${colors.border}` }}>
        {[['1. 选择文件', 1], ['2. 预览确认', 2], ['3. 确认导入', 3]].map(([label, s]) => {
          const sNum = s as 1 | 2 | 3;
          const active = step === sNum;
          const done = step > sNum;
          return (
            <div key={sNum} onClick={() => done && setStep(sNum)} style={{
              padding: '10px 20px', fontSize: 14,
              fontWeight: active ? 600 : 400,
              color: active ? colors.primary : done ? colors.success : colors.muted,
              borderBottom: active ? `2px solid ${colors.primary}` : '2px solid transparent',
              cursor: done ? 'pointer' : 'default',
            }}>
              {done ? '✓ ' : ''}{label}
            </div>
          );
        })}
      </div>

      {/* ──────────────── STEP 1 ──────────────── */}
      {step === 1 && (
        <form onSubmit={handleUpload} style={{ maxWidth: 520 }}>
          <div style={{ marginBottom: 16 }}>
            <label style={styles.label}>账户 *</label>
            <select value={accountId} onChange={e => setAccountId(e.target.value)} style={S.select}>
              {accounts.map(a => (
                <option key={a.id} value={String(a.id)}>
                  {a.holder_name || a.account_no} ({a.broker})
                </option>
              ))}
            </select>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={styles.label}>文件格式</label>
            <select value={source} onChange={e => setSource(e.target.value)} style={S.select}>
              {SOURCES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={styles.label}>上传文件 * (.csv)</label>
            <input type="file" accept=".csv,.xlsx" onChange={e => setFile(e.target.files?.[0] || null)} style={styles.input} disabled={uploading} />
          </div>
          <button type="submit" style={S.btn} disabled={uploading || !file || !canImport}>
            {uploading ? '解析中…' : '上传并解析'}
          </button>
          {!canImport && <p style={{ marginTop: 8, fontSize: 13, color: colors.muted }}>需要导入权限</p>}

          {batches.length > 0 && (
            <div style={{ marginTop: 32 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>历史导入记录</h3>
              <table style={styles.table}>
                <thead>
                  <tr>{['ID', '账户', '状态', '行数', ''].map(h => <th key={h} style={styles.th}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {batches.slice(0, 10).map((b, i) => (
                    <tr key={b.id} style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb' }}>
                      <td style={styles.td}>{b.id}</td>
                      <td style={styles.td}>{accounts.find(a => a.id === b.account_id)?.account_no || b.account_id}</td>
                      <td style={styles.td}>
                        <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: (STATUS_COLORS[b.status] || colors.muted) + '22', color: STATUS_COLORS[b.status] || colors.muted }}>
                          {b.status}
                        </span>
                      </td>
                      <td style={styles.td}>{b.row_count || '—'}</td>
                      <td style={styles.td}>{(b as any).imported_at ? String((b as any).imported_at).slice(0, 10) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </form>
      )}

      {/* ──────────────── STEP 2 ──────────────── */}
      {step === 2 && (
        <div>
          <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${colors.border}`, marginBottom: 16 }}>
            {TABS.map(t => {
              const count = tabCounts[t] || 0;
              if (count === 0 && t !== 'TRADE') return null;
              return (
                <button key={t} onClick={() => setActiveTab(t)} style={{
                  padding: '8px 16px', fontSize: 14, background: 'none', border: 'none',
                  borderBottom: activeTab === t ? `2px solid ${t === 'OTHER' ? colors.warning : colors.primary}` : '2px solid transparent',
                  color: t === 'OTHER' ? colors.warning : activeTab === t ? colors.primary : colors.muted,
                  cursor: 'pointer', fontWeight: activeTab === t ? 600 : 400,
                }}>
                  {CATEGORY_TAB_MAP[t] || t}
                  {count > 0 && (
                    <span style={{ marginLeft: 6, fontSize: 12, background: t === 'OTHER' ? '#fef3c7' : '#eff6ff', color: t === 'OTHER' ? '#92400e' : '#1d4ed8', padding: '1px 6px', borderRadius: 10 }}>
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {activeTab === 'OTHER' && tabCounts['OTHER'] > 0 && (
            <div style={{ marginBottom: 12 }}>
              <button onClick={skipAllOther} style={{ ...S.btn, background: '#f3f4f6', color: colors.text, border: `1px solid ${colors.border}` }}>
                全部跳过待处理
              </button>
              <span style={{ marginLeft: 12, fontSize: 13, color: colors.muted }}>这些行无法自动识别类型，请手动指定或跳过</span>
            </div>
          )}

          {visibleRows.length === 0 ? (
            <p style={{ color: colors.muted, fontSize: 14 }}>此分类无记录</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {['', '日期', '类型', '代码', '数量', '价格', '币种', '净额', ''].map((h, i) => (
                      <th key={i} style={{ ...styles.th, textAlign: i === 7 ? 'right' : 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row, i) => {
                    const net = netAmount(row);
                    const isPos = net > 0;
                    return (
                      <tr key={row.index} style={{ background: row.is_other ? '#fffbeb' : i % 2 === 0 ? '#fff' : '#f9fafb', opacity: row.selected ? 1 : 0.45 }}>
                        <td style={styles.td}>
                          <input type="checkbox" checked={row.selected} onChange={() => toggleRowSelected(row.index)} />
                        </td>
                        <td style={styles.td}>{row.trade_date?.slice(0, 10)}</td>
                        <td style={styles.td}>
                          <select
                            value={row.tx_type}
                            onChange={e => updateRowType(row.index, e.target.value)}
                            style={{ fontSize: 12, padding: '2px 4px', borderRadius: 4, border: `1px solid ${colors.border}` }}
                          >
                            {TX_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                          </select>
                        </td>
                        <td style={styles.td}>{row.asset_code || '—'}</td>
                        <td style={styles.td}>{row.quantity?.toLocaleString() || '—'}</td>
                        <td style={styles.td}>{row.price?.toFixed(4) || '—'}</td>
                        <td style={styles.td}>{row.currency}</td>
                        <td style={{ ...styles.td, textAlign: 'right', fontWeight: 600, color: isPos ? '#166534' : net < 0 ? '#b91c1c' : colors.text }}>
                          {net !== 0 ? `${isPos ? '+' : ''}${net.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
                        </td>
                        <td style={styles.td}>
                          <button
                            onClick={() => setEditingRow({ ...row })}
                            style={{ fontSize: 12, padding: '2px 8px', background: '#f3f4f6', border: `1px solid ${colors.border}`, borderRadius: 4, cursor: 'pointer' }}
                          >
                            编辑
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
            <button onClick={() => setStep(1)} style={{ ...S.btn, background: '#f3f4f6', color: colors.text, border: `1px solid ${colors.border}` }}>
              返回
            </button>
            <button onClick={() => setStep(3)} style={S.btn}>
              下一步：确认导入 ({selectedCount} 笔)
            </button>
          </div>
        </div>
      )}

      {/* ──────────────── STEP 3 ──────────────── */}
      {step === 3 && (
        <div style={{ maxWidth: 520 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>即将导入</h3>
          <div style={{ background: '#f9fafb', border: `1px solid ${colors.border}`, borderRadius: 8, padding: 20, marginBottom: 20 }}>
            {TABS.map(t => {
              const cnt = previewRows.filter(r => tabForRow(r) === t && r.selected).length;
              if (!cnt) return null;
              return (
                <div key={t} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 14 }}>
                  <span style={{ color: colors.muted }}>{CATEGORY_TAB_MAP[t] || t}</span>
                  <span style={{ fontWeight: 600 }}>{cnt} 笔</span>
                </div>
              );
            })}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 14, color: colors.muted }}>
              <span>跳过</span>
              <span>{previewRows.filter(r => !r.selected).length} 笔</span>
            </div>
            {assetCodes.length > 0 && (
              <div style={{ marginTop: 12, fontSize: 13, color: colors.muted }}>
                涉及资产：{assetCodes.slice(0, 8).join(' / ')}{assetCodes.length > 8 ? ' …' : ''}
              </div>
            )}
            {dates.length > 0 && (
              <div style={{ fontSize: 13, color: colors.muted }}>
                日期范围：{dates[0]?.slice(0, 10)} 至 {dates[dates.length - 1]?.slice(0, 10)}
              </div>
            )}
            {previewRows.length === 0 && batchId && (
              <div style={{ fontSize: 14 }}>批次 #{batchId} 已上传，点击确认写入</div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={() => setStep(2)} style={{ ...S.btn, background: '#f3f4f6', color: colors.text, border: `1px solid ${colors.border}` }} disabled={previewRows.length === 0}>
              返回修改
            </button>
            <button onClick={handleConfirm} style={S.btn} disabled={confirming}>
              {confirming ? '写入中…' : `确认导入${selectedCount > 0 ? ` ${selectedCount} 笔` : ''}`}
            </button>
          </div>
        </div>
      )}

      {/* ──────────────── Edit Row Modal ──────────────── */}
      {editingRow && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 10, padding: 24, width: 480, maxHeight: '80vh', overflowY: 'auto' }}>
            <h3 style={{ marginTop: 0, marginBottom: 16 }}>编辑交易记录</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={styles.label}>交易类型</label>
                <select value={editingRow.tx_type} onChange={e => setEditingRow({ ...editingRow, tx_type: e.target.value })} style={S.select}>
                  {TX_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label style={styles.label}>日期</label>
                <input type="date" value={editingRow.trade_date?.slice(0, 10)} onChange={e => setEditingRow({ ...editingRow, trade_date: e.target.value })} style={styles.input} />
              </div>
              <div>
                <label style={styles.label}>资产代码</label>
                <input value={editingRow.asset_code || ''} onChange={e => setEditingRow({ ...editingRow, asset_code: e.target.value })} style={styles.input} />
              </div>
              <div>
                <label style={styles.label}>数量</label>
                <input type="number" value={editingRow.quantity ?? ''} onChange={e => setEditingRow({ ...editingRow, quantity: parseFloat(e.target.value) || undefined })} style={styles.input} />
              </div>
              <div>
                <label style={styles.label}>成交价格</label>
                <input type="number" step="0.0001" value={editingRow.price ?? ''} onChange={e => setEditingRow({ ...editingRow, price: parseFloat(e.target.value) || undefined })} style={styles.input} />
              </div>
              <div>
                <label style={styles.label}>币种</label>
                <input value={editingRow.currency} onChange={e => setEditingRow({ ...editingRow, currency: e.target.value })} style={styles.input} />
              </div>
              <div>
                <label style={styles.label}>佣金</label>
                <input type="number" step="0.01" value={editingRow.commission ?? ''} onChange={e => setEditingRow({ ...editingRow, commission: parseFloat(e.target.value) || undefined })} style={styles.input} />
              </div>
              <div>
                <label style={styles.label}>交易税</label>
                <input type="number" step="0.01" value={editingRow.transaction_fee ?? ''} onChange={e => setEditingRow({ ...editingRow, transaction_fee: parseFloat(e.target.value) || undefined })} style={styles.input} />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <label style={styles.label}>备注</label>
                <input value={editingRow.description || ''} onChange={e => setEditingRow({ ...editingRow, description: e.target.value })} style={styles.input} />
              </div>
            </div>
            <div style={{ fontSize: 13, color: colors.muted, marginTop: 12 }}>
              净现金影响：{netAmount(editingRow).toLocaleString('en-US', { minimumFractionDigits: 2 })} {editingRow.currency}
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 16 }}>
              <button onClick={() => setEditingRow(null)} style={{ ...S.btn, background: '#f3f4f6', color: colors.text, border: `1px solid ${colors.border}` }}>取消</button>
              <button onClick={() => {
                if (!editingRow) return;
                setPreviewRows(prev => prev.map(r => r.index === editingRow.index ? editingRow : r));
                setEditingRow(null);
              }} style={S.btn}>保存</button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if (!auth || 'redirect' in auth) return { redirect: { destination: '/login', permanent: false } };

  try {
    const { getAccounts, getImportBatches } = await import('../lib/api');
    const [acctResp, batches] = await Promise.all([
      getAccounts({ size: 100, accessToken: auth.accessToken }),
      getImportBatches({ accessToken: auth.accessToken }).catch(() => [] as ImportBatch[]),
    ]);
    return { props: { accounts: acctResp.items || [], batches: Array.isArray(batches) ? batches.slice(0, 20) : [] } };
  } catch (e: unknown) {
    return { props: { accounts: [], batches: [], error: String(e instanceof Error ? e.message : e) } };
  }
}
