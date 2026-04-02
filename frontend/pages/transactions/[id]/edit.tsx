import { useRouter } from 'next/router';
import { useState } from 'react';
import Layout from '../../../components/Layout';
import {
  Account,
  Transaction,
  deleteTransaction,
  getAccounts,
  updateTransaction,
} from '../../../lib/api';
import { requirePageAuth } from '../../../lib/pageAuth';
import { colors, styles } from '../../../lib/ui';

type Props = {
  tx: Transaction;
  accounts: Account[];
  accessToken: string;
};

export default function EditTransactionPage({ tx, accounts, accessToken }: Props) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  // Editable fields
  const [tradeDate, setTradeDate] = useState(tx.trade_date);
  const [settleDate, setSettleDate] = useState(tx.settle_date || '');
  const [currency, setCurrency] = useState(tx.currency);
  const [description, setDescription] = useState(tx.description || '');
  const [assetCode, setAssetCode] = useState(tx.asset_code || '');
  const [assetName, setAssetName] = useState(tx.asset_name || '');
  const [quantity, setQuantity] = useState(tx.quantity != null ? String(tx.quantity) : '');
  const [price, setPrice] = useState(tx.price != null ? String(tx.price) : '');
  const [grossAmount, setGrossAmount] = useState(tx.gross_amount != null ? String(tx.gross_amount) : '');
  const [commission, setCommission] = useState(tx.commission != null ? String(tx.commission) : '');
  const [txFee, setTxFee] = useState(tx.transaction_fee != null ? String(tx.transaction_fee) : '');
  const [otherFee, setOtherFee] = useState(tx.other_fee != null ? String(tx.other_fee) : '');
  const [realizedPnl, setRealizedPnl] = useState(tx.realized_pnl != null ? String(tx.realized_pnl) : '');
  const [counterpartyAccount, setCounterpartyAccount] = useState(tx.counterparty_account || '');
  const [accrualStart, setAccrualStart] = useState(tx.accrual_period_start || '');
  const [accrualEnd, setAccrualEnd] = useState(tx.accrual_period_end || '');

  const num = (v: string) => v !== '' ? Number(v) : undefined;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await updateTransaction(tx.id, {
        trade_date: tradeDate,
        settle_date: settleDate || undefined,
        currency,
        description: description || undefined,
        asset_code: assetCode ? assetCode.toUpperCase() : undefined,
        asset_name: assetName || undefined,
        quantity: num(quantity),
        price: num(price),
        gross_amount: num(grossAmount),
        commission: num(commission),
        transaction_fee: num(txFee),
        other_fee: num(otherFee),
        realized_pnl: num(realizedPnl),
        counterparty_account: counterpartyAccount || undefined,
        accrual_period_start: accrualStart || undefined,
        accrual_period_end: accrualEnd || undefined,
      }, accessToken);
      router.push('/transactions');
    } catch (err: any) {
      setError(err?.message || '保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`确认删除交易 #${tx.id}？此操作不可撤销。`)) return;
    setDeleting(true);
    try {
      await deleteTransaction(tx.id, accessToken);
      router.push('/transactions');
    } catch (err: any) {
      setError(err?.message || '删除失败');
      setDeleting(false);
    }
  };

  const inputStyle = {
    padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`,
    fontSize: 13, width: '100%', boxSizing: 'border-box' as const,
  };
  const labelStyle = { fontSize: 12, color: colors.muted, display: 'block', marginBottom: 4 };
  const fieldWrap = { marginBottom: 14 };

  const CURRENCIES = ['USD', 'HKD', 'CNY', 'EUR', 'SGD', 'AUD'];

  return (
    <Layout title="编辑交易" subtitle={`#${tx.id} · ${tx.tx_category} / ${tx.tx_type}`} requiredPermission="accounts.write">
      <div style={{ marginBottom: 12 }}>
        <button onClick={() => router.push('/transactions')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: colors.primary, fontSize: 13 }}>
          ← 返回交易列表
        </button>
      </div>

      {/* Read-only info */}
      <div style={{ ...styles.card, marginBottom: 16, padding: '10px 16px', background: '#f8fafc' }}>
        <div style={{ display: 'flex', gap: 20, fontSize: 13, flexWrap: 'wrap' }}>
          <span>ID: <strong>#{tx.id}</strong></span>
          <span>分类: <strong>{tx.tx_category}</strong></span>
          <span>类型: <strong>{tx.tx_type}</strong></span>
          <span>账户: <strong>#{tx.account_id}</strong></span>
          <span>来源: <strong>{tx.source || 'manual'}</strong></span>
        </div>
        {tx.source !== 'manual' && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#d97706' }}>
            ⚠️ 此记录来源为 {tx.source}，编辑可能影响批次一致性。
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Column 1 */}
          <div style={styles.card}>
            <h4 style={{ margin: '0 0 12px', fontSize: 14, color: colors.muted }}>基本信息</h4>

            <div style={fieldWrap}>
              <label style={labelStyle}>交易日期 *</label>
              <input type="date" value={tradeDate} onChange={e => setTradeDate(e.target.value)} required style={inputStyle} />
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>结算日期</label>
              <input type="date" value={settleDate} onChange={e => setSettleDate(e.target.value)} style={inputStyle} />
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>货币</label>
              <select value={currency} onChange={e => setCurrency(e.target.value)} style={inputStyle}>
                {CURRENCIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>描述/备注</label>
              <textarea value={description} onChange={e => setDescription(e.target.value)}
                rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>对方账户（划转）</label>
              <input type="text" value={counterpartyAccount} onChange={e => setCounterpartyAccount(e.target.value)} style={inputStyle} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <label style={labelStyle}>计息起始</label>
                <input type="date" value={accrualStart} onChange={e => setAccrualStart(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>计息截止</label>
                <input type="date" value={accrualEnd} onChange={e => setAccrualEnd(e.target.value)} style={inputStyle} />
              </div>
            </div>
          </div>

          {/* Column 2 */}
          <div style={styles.card}>
            <h4 style={{ margin: '0 0 12px', fontSize: 14, color: colors.muted }}>金额 / 资产</h4>

            <div style={fieldWrap}>
              <label style={labelStyle}>资产代码</label>
              <input type="text" value={assetCode} onChange={e => setAssetCode(e.target.value)} style={inputStyle} />
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>资产名称</label>
              <input type="text" value={assetName} onChange={e => setAssetName(e.target.value)} style={inputStyle} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
              <div>
                <label style={labelStyle}>数量</label>
                <input type="number" step="any" value={quantity} onChange={e => setQuantity(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>价格</label>
                <input type="number" step="any" value={price} onChange={e => setPrice(e.target.value)} style={inputStyle} />
              </div>
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>成交金额 (gross_amount)</label>
              <input type="number" step="any" value={grossAmount} onChange={e => setGrossAmount(e.target.value)} style={inputStyle} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
              <div>
                <label style={labelStyle}>佣金</label>
                <input type="number" step="any" value={commission} onChange={e => setCommission(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>交易税</label>
                <input type="number" step="any" value={txFee} onChange={e => setTxFee(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>其他费用</label>
                <input type="number" step="any" value={otherFee} onChange={e => setOtherFee(e.target.value)} style={inputStyle} />
              </div>
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>已实现盈亏</label>
              <input type="number" step="any" value={realizedPnl} onChange={e => setRealizedPnl(e.target.value)} style={inputStyle} />
            </div>
          </div>
        </div>

        {error && <div style={{ color: '#dc2626', fontSize: 13, marginTop: 12, padding: '8px 12px', background: '#fef2f2', borderRadius: 6 }}>{error}</div>}

        <div style={{ display: 'flex', gap: 12, marginTop: 16, justifyContent: 'space-between' }}>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            style={{
              padding: '10px 20px', borderRadius: 6, border: '1px solid #fca5a5',
              background: '#fef2f2', color: '#dc2626', cursor: deleting ? 'not-allowed' : 'pointer', fontSize: 14,
            }}
          >
            {deleting ? '删除中...' : '删除此记录'}
          </button>
          <div style={{ display: 'flex', gap: 12 }}>
            <button type="button" onClick={() => router.push('/transactions')} style={{
              padding: '10px 20px', borderRadius: 6, border: `1px solid ${colors.border}`, background: 'white', cursor: 'pointer', fontSize: 14,
            }}>取消</button>
            <button type="submit" disabled={submitting} style={{
              padding: '10px 24px', borderRadius: 6, border: 'none',
              background: submitting ? '#94a3b8' : colors.primary, color: 'white',
              cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 14,
            }}>
              {submitting ? '保存中...' : '保存修改'}
            </button>
          </div>
        </div>
      </form>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  const txId = Number(context.params?.id);
  if (!txId || isNaN(txId)) return { redirect: { destination: '/transactions', permanent: false } };

  try {
    const { fetchJson } = await import('../../../lib/api');
    const [tx, acctData] = await Promise.all([
      (fetchJson as any)(`/transaction/${txId}`, { accessToken: auth.accessToken }),
      getAccounts({ size: 100, accessToken: auth.accessToken }),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        tx,
        accounts: acctData.items ?? [],
        accessToken: auth.accessToken,
      },
    };
  } catch (e: any) {
    return { redirect: { destination: '/transactions', permanent: false } };
  }
}
