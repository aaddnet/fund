/**
 * /cash — Cash Ledger View (V4.3)
 *
 * Read-only account ledger: balance summary + chronological cash flow.
 * Balances and flow are calculated in real-time from the Transaction table.
 */
import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { Account } from '../lib/api';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

// Inline style helpers not in the legacy styles object
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

type CurrencyBalance = {
  currency: string;
  balance: number;
};

type BalanceResponse = {
  account_id: number;
  as_of_date: string;
  balances: Record<string, number>;
};

type FlowEntry = {
  tx_id: number;
  trade_date: string;
  settle_date: string | null;
  tx_category: string;
  tx_type: string;
  description: string | null;
  currency: string;
  delta: number;
  balance_after: number;
};

type Props = {
  accounts: Account[];
  apiBase: string;
  error?: string;
};

const TX_TYPE_LABELS: Record<string, string> = {
  stock_buy: '股票买入', stock_sell: '股票卖出',
  option_buy: '期权买入', option_sell: '期权卖出',
  deposit_eft: '存款入金', deposit_transfer: '存款划转',
  withdrawal: '提款', dividend: '股息', pil: '代付股息',
  dividend_fee: '股息税费', interest_debit: '融资利息',
  interest_credit: '利息收入', adr_fee: 'ADR费用',
  other_fee: '其他费用', adjustment: '调整', fx_trade: '换汇',
  lending_income: '出借收入', lending_out: '证券出借',
  lending_return: '证券归还',
};

const CURRENCIES = ['USD', 'HKD', 'CNH', 'EUR', 'GBP'];

function fmtNum(n: number, d = 2) {
  return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}

export default function CashPage({ accounts, apiBase, error }: Props) {
  const [accountId, setAccountId] = useState<string>(String(accounts[0]?.id ?? ''));
  const [asOfDate, setAsOfDate] = useState<string>(() => new Date().toISOString().slice(0, 10));

  const [balances, setBalances] = useState<CurrencyBalance[]>([]);
  const [flowCurrency, setFlowCurrency] = useState<string>('USD');
  const [flowStart, setFlowStart] = useState<string>('');
  const [flowEnd, setFlowEnd] = useState<string>('');
  const [flowEntries, setFlowEntries] = useState<FlowEntry[]>([]);

  const [balanceLoading, setBalanceLoading] = useState(false);
  const [flowLoading, setFlowLoading] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);

  async function fetchBalances() {
    if (!accountId) return;
    setBalanceLoading(true);
    setBalanceError(null);
    try {
      const res = await fetch(`${apiBase}/cash/balance?account_id=${accountId}&as_of_date=${asOfDate}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BalanceResponse = await res.json();
      const entries = Object.entries(data.balances)
        .map(([currency, balance]) => ({ currency, balance }))
        .sort((a, b) => (a.balance !== 0 ? -1 : 1) - (b.balance !== 0 ? -1 : 1) || a.currency.localeCompare(b.currency));
      setBalances(entries);
    } catch (e: unknown) {
      setBalanceError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setBalanceLoading(false);
    }
  }

  async function fetchFlow() {
    if (!accountId) return;
    setFlowLoading(true);
    try {
      const res = await fetch(`${apiBase}/cash/flow?account_id=${accountId}&currency=${flowCurrency}&limit=500`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      let data: FlowEntry[] = await res.json();
      if (flowStart) data = data.filter(e => e.trade_date >= flowStart);
      if (flowEnd) data = data.filter(e => e.trade_date <= flowEnd + 'T99');
      setFlowEntries(data);
    } catch {
      setFlowEntries([]);
    } finally {
      setFlowLoading(false);
    }
  }

  useEffect(() => { void fetchBalances(); }, [accountId, asOfDate]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void fetchFlow(); }, [accountId, flowCurrency, flowStart, flowEnd]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleExport() {
    window.open(`${apiBase}/cash/flow/export?account_id=${accountId}&currency=${flowCurrency}`, '_blank');
  }

  return (
    <Layout title="现金账本">
      {error && (
        <div style={{ padding: '12px 16px', background: '#fee2e2', color: '#991b1b', borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Header controls */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 24, flexWrap: 'wrap' }}>
        <div>
          <label style={styles.label}>账户</label>
          <select value={accountId} onChange={e => setAccountId(e.target.value)} style={S.select}>
            {accounts.map(a => (
              <option key={a.id} value={String(a.id)}>
                {a.holder_name || a.account_no} ({a.broker})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label style={styles.label}>截至日期</label>
          <input type="date" value={asOfDate} onChange={e => setAsOfDate(e.target.value)} style={styles.input} />
        </div>
        <button onClick={() => { void fetchBalances(); }} style={S.btn}>刷新余额</button>
      </div>

      {/* Balance cards */}
      <div style={{ marginBottom: 28 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: colors.text, marginBottom: 12 }}>当前余额汇总</h3>
        {balanceLoading && <p style={{ color: colors.muted, fontSize: 14 }}>计算中…</p>}
        {balanceError && <p style={{ color: colors.danger, fontSize: 14 }}>⚠️ {balanceError} — 请确认后端已升级至 V4.3</p>}
        {!balanceLoading && !balanceError && balances.length === 0 && (
          <p style={{ color: colors.muted, fontSize: 14 }}>暂无余额记录（该账户还没有交易记录）</p>
        )}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {balances.map(({ currency, balance }) => {
            const isNeg = balance < 0;
            return (
              <div key={currency} style={{
                padding: '16px 20px', borderRadius: 8, minWidth: 180,
                background: isNeg ? '#fff1f2' : '#f0fdf4',
                border: `1px solid ${isNeg ? '#fca5a5' : '#86efac'}`,
              }}>
                <div style={{ fontSize: 13, color: colors.muted, marginBottom: 4 }}>
                  {currency}
                  {isNeg && <span style={{ marginLeft: 8, fontSize: 11, color: '#b91c1c', fontWeight: 600, background: '#fee2e2', padding: '1px 6px', borderRadius: 4 }}>融资负债</span>}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: isNeg ? '#b91c1c' : '#166534' }}>
                  {isNeg ? '-' : ''}{fmtNum(Math.abs(balance))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Flow ledger */}
      <div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 12, flexWrap: 'wrap' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: colors.text, margin: 0 }}>现金流水明细</h3>
          <div>
            <label style={styles.label}>币种</label>
            <select value={flowCurrency} onChange={e => setFlowCurrency(e.target.value)} style={{ ...S.select, width: 80 }}>
              {CURRENCIES.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={styles.label}>开始</label>
            <input type="date" value={flowStart} onChange={e => setFlowStart(e.target.value)} style={styles.input} />
          </div>
          <div>
            <label style={styles.label}>结束</label>
            <input type="date" value={flowEnd} onChange={e => setFlowEnd(e.target.value)} style={styles.input} />
          </div>
          <button onClick={handleExport} style={{ ...S.btn, background: '#f3f4f6', color: colors.text, border: `1px solid ${colors.border}` }}>
            导出 CSV
          </button>
        </div>

        {flowLoading && <p style={{ color: colors.muted, fontSize: 14 }}>加载中…</p>}
        {!flowLoading && flowEntries.length === 0 && <p style={{ color: colors.muted, fontSize: 14 }}>无流水记录</p>}
        {!flowLoading && flowEntries.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>{['日期', '类型', '描述', '变动', '余额'].map(h => <th key={h} style={styles.th}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {flowEntries.map((e, i) => {
                  const isPos = e.delta > 0;
                  return (
                    <tr key={e.tx_id} style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb' }}>
                      <td style={styles.td}>{e.trade_date?.slice(0, 10)}</td>
                      <td style={styles.td}>
                        <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: '#f3f4f6', color: colors.text }}>
                          {TX_TYPE_LABELS[e.tx_type] || e.tx_type}
                        </span>
                      </td>
                      <td style={{ ...styles.td, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {e.description || '—'}
                      </td>
                      <td style={{ ...styles.td, textAlign: 'right', fontWeight: 600, color: isPos ? '#166534' : '#b91c1c' }}>
                        {isPos ? '+' : ''}{fmtNum(e.delta)}
                      </td>
                      <td style={{ ...styles.td, textAlign: 'right', color: e.balance_after < 0 ? '#b91c1c' : colors.text }}>
                        {fmtNum(e.balance_after)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if (!auth || 'redirect' in auth) return { redirect: { destination: '/login', permanent: false } };

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000';
  try {
    const { getAccounts } = await import('../lib/api');
    const acctResp = await getAccounts({ size: 100, accessToken: auth.accessToken });
    return { props: { accounts: acctResp.items || [], apiBase } };
  } catch (e: unknown) {
    return { props: { accounts: [], apiBase, error: String(e instanceof Error ? e.message : e) } };
  }
}
