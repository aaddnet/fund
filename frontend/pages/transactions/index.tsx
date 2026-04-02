import Link from 'next/link';
import { useMemo, useState } from 'react';
import Layout from '../../components/Layout';
import ProductTable from '../../components/ProductTable';
import {
  Account,
  Transaction,
  deleteTransaction,
  getAccounts,
  getTransactions,
} from '../../lib/api';
import { useI18n } from '../../lib/i18n';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, styles } from '../../lib/ui';

type Props = {
  accounts: Account[];
  transactions: Transaction[];
  error?: string;
};

const CATEGORY_COLORS: Record<string, string> = {
  TRADE:     '#1d4ed8',
  EQUITY:    '#1d4ed8',
  CASH:      '#15803d',
  FX:        '#9333ea',
  LENDING:   '#c2410c',
  SECURITIES_LENDING: '#c2410c',
  ACCRUAL:   '#6b7280',
  CORPORATE: '#d97706',
  MARGIN:    '#b45309',
};

const TX_TYPE_LABELS: Record<string, string> = {
  stock_buy: '买入', stock_sell: '卖出',
  option_buy: '期权买入', option_sell: '期权卖出',
  option_expire: '期权作废', option_exercise: '期权行权',
  deposit_eft: '入金-EFT', deposit_transfer: '入金-划转',
  withdrawal: '出金',
  dividend: '股息', pil: 'PIL', dividend_fee: '股息手续费',
  interest_debit: '融资利息', interest_credit: '账户利息',
  adr_fee: 'ADR费', other_fee: '其他费用', adjustment: '调整',
  fx_trade: '换汇', fx: '换汇',
  lending_out: '出借', lending_return: '归还出借', lending_income: '出借收益',
  interest_accrual: '利息应计', dividend_accrual: '股息应计',
  stock_split: '股票拆分', reverse_split: '反向拆分',
  rights_issue: '配股', spinoff: '分拆', merger: '合并',
  buy: '买入', sell: '卖出',
};

export default function TransactionsPage({ accounts, transactions, error }: Props) {
  const { t } = useI18n();
  const [accountFilter, setAccountFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [assetFilter, setAssetFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [deleting, setDeleting] = useState<number | null>(null);

  const accountMap = useMemo(() => {
    const m = new Map<number, Account>();
    for (const a of accounts) m.set(a.id, a);
    return m;
  }, [accounts]);

  const filtered = useMemo(() => {
    return transactions.filter(tx => {
      if (accountFilter && String(tx.account_id) !== accountFilter) return false;
      if (categoryFilter) {
        const cats = [categoryFilter];
        if (categoryFilter === 'TRADE') cats.push('EQUITY');
        if (categoryFilter === 'LENDING') cats.push('SECURITIES_LENDING');
        if (!cats.includes(tx.tx_category)) return false;
      }
      if (assetFilter && !(tx.asset_code || '').toLowerCase().includes(assetFilter.toLowerCase())) return false;
      if (dateFrom && tx.trade_date < dateFrom) return false;
      if (dateTo && tx.trade_date > dateTo) return false;
      return true;
    });
  }, [transactions, accountFilter, categoryFilter, assetFilter, dateFrom, dateTo]);

  const fmt = (n: number | null | undefined, dec = 2) =>
    n == null ? '—' : Number(n).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });

  const netAmount = (tx: Transaction): number | null => {
    if (tx.gross_amount != null) {
      return (tx.gross_amount || 0) + (tx.commission || 0) + (tx.transaction_fee || 0) + (tx.other_fee || 0);
    }
    if (tx.amount != null) return (tx.amount || 0) + (tx.fee || 0);
    return null;
  };

  const handleDelete = async (tx: Transaction) => {
    if (!confirm(`确认删除交易 #${tx.id}？此操作不可撤销。`)) return;
    setDeleting(tx.id);
    try {
      await deleteTransaction(tx.id);
      window.location.reload();
    } catch (e: any) {
      alert(e?.message || '删除失败');
    } finally {
      setDeleting(null);
    }
  };

  const categories = ['TRADE', 'CASH', 'FX', 'LENDING', 'ACCRUAL', 'CORPORATE'];

  return (
    <Layout title="交易管理" subtitle="所有账户的完整交易记录" requiredPermission="accounts.read">
      {error && <div style={{ ...styles.card, color: colors.danger, marginBottom: 16 }}>{error}</div>}

      {/* Toolbar */}
      <div style={{ ...styles.card, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {/* Account filter */}
          <div>
            <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>账户</div>
            <select
              value={accountFilter}
              onChange={e => setAccountFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">全部账户</option>
              {accounts.map(a => (
                <option key={a.id} value={String(a.id)}>{a.broker} · {a.account_no}</option>
              ))}
            </select>
          </div>

          {/* Category filter */}
          <div>
            <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>类型</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                onClick={() => setCategoryFilter('')}
                style={{
                  padding: '4px 10px', borderRadius: 4, border: `1px solid ${colors.border}`,
                  background: categoryFilter === '' ? colors.primary : 'white',
                  color: categoryFilter === '' ? 'white' : colors.muted,
                  cursor: 'pointer', fontSize: 12,
                }}
              >全部</button>
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat === categoryFilter ? '' : cat)}
                  style={{
                    padding: '4px 10px', borderRadius: 4, border: `1px solid ${colors.border}`,
                    background: categoryFilter === cat ? (CATEGORY_COLORS[cat] || '#6b7280') : 'white',
                    color: categoryFilter === cat ? 'white' : colors.muted,
                    cursor: 'pointer', fontSize: 12, fontWeight: 600,
                  }}
                >{cat}</button>
              ))}
            </div>
          </div>

          {/* Asset filter */}
          <div>
            <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>资产代码</div>
            <input
              type="text"
              value={assetFilter}
              onChange={e => setAssetFilter(e.target.value)}
              placeholder="如 AAPL / 175"
              style={{ padding: '6px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13, width: 120 }}
            />
          </div>

          {/* Date range */}
          <div>
            <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>起始日</div>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }} />
          </div>
          <div>
            <div style={{ fontSize: 12, color: colors.muted, marginBottom: 4 }}>截止日</div>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }} />
          </div>

          <div style={{ marginLeft: 'auto' }}>
            <Link href="/transactions/new" style={{
              display: 'inline-block', padding: '8px 16px', borderRadius: 6,
              background: colors.primary, color: 'white', textDecoration: 'none',
              fontWeight: 600, fontSize: 14,
            }}>
              + 新增交易
            </Link>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ ...styles.card, marginBottom: 16, padding: '10px 16px' }}>
        <div style={{ fontSize: 13, color: colors.muted }}>
          共 <strong>{filtered.length}</strong> 条
          {accountFilter && <span>（账户 #{accountFilter}）</span>}
          {categoryFilter && <span> · {categoryFilter}</span>}
        </div>
      </div>

      {/* Table */}
      <div style={styles.card}>
        <ProductTable
          emptyText="暂无交易记录"
          rows={filtered}
          columns={[
            { key: 'date', title: '交易日期', render: r => r.trade_date },
            { key: 'acct', title: '账户', render: r => {
              const a = accountMap.get(r.account_id);
              return a ? <span style={{ fontSize: 12 }}>{a.broker} {a.account_no}</span> : `#${r.account_id}`;
            }},
            { key: 'cat', title: '分类', render: r => {
              const cat = r.tx_category || 'EQUITY';
              return (
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                  background: CATEGORY_COLORS[cat] || '#6b7280', color: '#fff',
                }}>{cat}</span>
              );
            }},
            { key: 'type', title: '类型', render: r => {
              const label = TX_TYPE_LABELS[r.tx_type] || r.tx_type;
              const isBuy = ['buy', 'stock_buy', 'option_buy', 'deposit_eft', 'deposit_transfer', 'dividend', 'interest_credit', 'lending_income'].includes(r.tx_type);
              const isSell = ['sell', 'stock_sell', 'withdrawal', 'interest_debit', 'adr_fee', 'dividend_fee', 'other_fee'].includes(r.tx_type);
              return <span style={{ color: isBuy ? '#16a34a' : isSell ? '#dc2626' : '#374151', fontWeight: 600, fontSize: 12 }}>{label}</span>;
            }},
            { key: 'asset', title: '资产', render: r => r.asset_code
              ? <strong>{r.asset_code}</strong>
              : <span style={{ color: colors.muted, fontSize: 12 }}>—</span>
            },
            { key: 'qty', title: '数量', render: r => r.quantity != null ? fmt(r.quantity, 2) : '—' },
            { key: 'price', title: '价格', render: r => r.price != null ? fmt(r.price, 4) : '—' },
            { key: 'cur', title: '货币', render: r => r.currency },
            { key: 'net', title: '净额', render: r => {
              const net = netAmount(r);
              if (net == null) return '—';
              const color = net > 0 ? '#15803d' : net < 0 ? '#dc2626' : '#374151';
              return <span style={{ color, fontWeight: 600 }}>{net > 0 ? '+' : ''}{fmt(net)}</span>;
            }},
            { key: 'src', title: '来源', render: r => (
              <span style={{ fontSize: 11, color: colors.muted }}>{r.source || 'manual'}</span>
            )},
            { key: 'ops', title: '操作', render: r => (
              <div style={{ display: 'flex', gap: 8 }}>
                <Link href={`/transactions/${r.id}/edit`} style={{ fontSize: 12, color: colors.primary, textDecoration: 'none' }}>编辑</Link>
                {r.source === 'manual' && (
                  <button
                    onClick={() => handleDelete(r)}
                    disabled={deleting === r.id}
                    style={{ fontSize: 12, color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                  >
                    {deleting === r.id ? '...' : '删除'}
                  </button>
                )}
              </div>
            )},
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  try {
    const [txData, acctData] = await Promise.all([
      getTransactions({ size: 200, accessToken: auth.accessToken }),
      getAccounts({ size: 100, accessToken: auth.accessToken }),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        transactions: txData.items ?? [],
        accounts: acctData.items ?? [],
      },
    };
  } catch (e: any) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        transactions: [],
        accounts: [],
        error: e?.message || 'Failed to load transactions.',
      },
    };
  }
}
