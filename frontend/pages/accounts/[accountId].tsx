import Link from 'next/link';
import { useMemo, useState } from 'react';
import Layout from '../../components/Layout';
import ProductTable from '../../components/ProductTable';
import {
  Account,
  AssetPrice,
  CashBalances,
  CashPosition,
  FXSummary,
  ImportBatch,
  Position,
  Transaction,
  getAccount,
  getCashBalances,
  getCashPositions,
  getFxSummary,
  getImportBatches,
  getPrices,
  getPositions,
  getTransactions,
} from '../../lib/api';
import { useI18n } from '../../lib/i18n';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, formatNumber, styles } from '../../lib/ui';

type Tab = 'positions' | 'transactions' | 'imports' | 'cash' | 'fx';

type Props = {
  account: Account;
  positions: Position[];
  transactions: Transaction[];
  imports: ImportBatch[];
  cashPositions: CashPosition[];
  cashBalances: CashBalances | null;
  fxSummary: FXSummary[];
  latestPrices: AssetPrice[];
  error?: string;
};

export default function Page({ account, positions, transactions, imports, cashPositions, cashBalances, fxSummary, latestPrices, error }: Props) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>('positions');

  // Use the latest snapshot per (asset_code, currency)
  const aggregatedPositions = useMemo(() => {
    const map = new Map<string, { asset_code: string; currency: string; quantity: number; average_cost: number; snapshot_date: string }>();
    for (const p of positions) {
      const key = `${p.asset_code}__${p.currency}`;
      const existing = map.get(key);
      if (!existing || p.snapshot_date > existing.snapshot_date) {
        map.set(key, {
          asset_code: p.asset_code,
          currency: p.currency,
          quantity: Number(p.quantity),
          average_cost: Number(p.average_cost || 0),
          snapshot_date: p.snapshot_date,
        });
      }
    }
    return Array.from(map.values())
      .filter(r => r.quantity !== 0)
      .sort((a, b) => a.asset_code.localeCompare(b.asset_code));
  }, [positions]);

  // Separate transactions by category
  const equityTxns = useMemo(() => transactions.filter(t => !t.tx_category || t.tx_category === 'EQUITY'), [transactions]);
  const fxTxns = useMemo(() => transactions.filter(t => t.tx_category === 'FX'), [transactions]);
  const cashTxns = useMemo(() => transactions.filter(t => t.tx_category === 'CASH' || t.tx_category === 'MARGIN'), [transactions]);

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'positions', label: t('tabPositions'), count: aggregatedPositions.length },
    { key: 'transactions', label: t('tabTransactions'), count: transactions.length },
    { key: 'cash', label: t('tabCash'), count: cashPositions.length },
    { key: 'fx', label: '换汇记录', count: fxTxns.length },
    { key: 'imports', label: t('tabImports'), count: imports.length },
  ];

  // Build price map: asset_code -> latest price_usd
  const priceMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of latestPrices) {
      map.set(p.asset_code.toUpperCase(), Number(p.price_usd));
    }
    return map;
  }, [latestPrices]);

  const totalPositionValue = useMemo(
    () => aggregatedPositions.reduce((sum, p) => {
      const mktPrice = priceMap.get(p.asset_code.toUpperCase());
      return sum + (mktPrice != null ? p.quantity * mktPrice : p.quantity * p.average_cost);
    }, 0),
    [aggregatedPositions, priceMap],
  );

  // Cash balances from V4 transaction-based calculation (preferred)
  // Fall back to snapshot-based cashPositions if not available
  const cashBalancesDisplay = useMemo(() => {
    if (cashBalances?.balances && Object.keys(cashBalances.balances).length > 0) {
      return Object.entries(cashBalances.balances)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([currency, amount]) => ({ currency, amount }));
    }
    // Fall back to snapshot-based cash
    const map = new Map<string, number>();
    for (const c of cashPositions) {
      map.set(c.currency, (map.get(c.currency) || 0) + Number(c.amount));
    }
    return Array.from(map.entries()).map(([currency, amount]) => ({ currency, amount }));
  }, [cashBalances, cashPositions]);

  const totalCashUSD = useMemo(
    () => cashBalancesDisplay.reduce((sum, c) => {
      // Simple sum (not FX-adjusted for display purposes)
      if (c.currency === 'USD') return sum + c.amount;
      return sum; // non-USD shown separately
    }, 0),
    [cashBalancesDisplay],
  );

  const fmt = (n: number | null | undefined, dec = 2) =>
    n == null ? '—' : Number(n).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });

  const txCategoryBadge = (tx: Transaction) => {
    const cat = tx.tx_category || 'EQUITY';
    const colors: Record<string, string> = {
      EQUITY: '#1d4ed8',
      CASH: '#15803d',
      FX: '#9333ea',
      MARGIN: '#b45309',
      CORPORATE: '#0f766e',
    };
    return (
      <span style={{
        fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
        background: colors[cat] || '#6b7280', color: '#fff',
      }}>{cat}</span>
    );
  };

  const txTypeBadge = (txType: string) => {
    const c = txType === 'buy' ? '#16a34a' : txType === 'sell' ? '#dc2626' : '#6b7280';
    return <span style={{ color: c, fontWeight: 600, fontSize: 12 }}>{txType.toUpperCase()}</span>;
  };

  return (
    <Layout title={t('accountDetailTitle')} subtitle={t('accountDetailSub')} requiredPermission="accounts.read">
      {error && <div style={{ ...styles.card, color: colors.danger, marginBottom: 16 }}>{error}</div>}

      {/* Account header */}
      <div style={{ ...styles.card, marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <Link href="/accounts" style={{ color: colors.primary, fontSize: 13, textDecoration: 'none' }}>← {t('backToAccounts')}</Link>
            <h2 style={{ margin: '8px 0 4px' }}>
              {account.broker} · {account.account_no}
            </h2>
            <div style={{ color: colors.muted, fontSize: 13 }}>
              {t('fund')}: <strong>{account.fund_name || `#${account.fund_id}`}</strong>
              {account.holder_name && <> · {t('accountHolder')}: <strong>{account.holder_name}</strong></>}
              {' · '}ID: #{account.id}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 20, fontSize: 13 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ color: colors.muted }}>{t('tabPositions')}</div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>{aggregatedPositions.length}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ color: colors.muted }}>{t('tabTransactions')}</div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>{transactions.length}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ color: colors.muted }}>Position Value</div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>${fmt(totalPositionValue)}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ color: colors.muted }}>{t('tabCash')} (USD)</div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>${fmt(totalCashUSD)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: `2px solid ${colors.border}` }}>
        {tabs.map(tb => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            style={{
              padding: '10px 18px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              fontWeight: tab === tb.key ? 700 : 400,
              color: tab === tb.key ? colors.primary : colors.muted,
              borderBottom: tab === tb.key ? `2px solid ${colors.primary}` : '2px solid transparent',
              marginBottom: -2,
              fontSize: 14,
            }}
          >
            {tb.label} ({tb.count})
          </button>
        ))}
      </div>

      {/* Positions tab */}
      {tab === 'positions' && (
        <div style={styles.card}>
          <div style={{ fontSize: 12, color: colors.muted, marginBottom: 8 }}>
            每个资产取最新快照日期的持仓数量和均价
          </div>
          <ProductTable
            emptyText={t('noPositions')}
            rows={aggregatedPositions}
            columns={[
              { key: 'asset', title: t('assetCode'), render: r => <strong>{r.asset_code}</strong> },
              { key: 'qty', title: t('quantity'), render: r => fmt(r.quantity, 4) },
              { key: 'avg', title: t('avgCost'), render: r => fmt(r.average_cost, 4) },
              { key: 'cur', title: 'Currency', render: r => r.currency },
              { key: 'cost_val', title: '成本市值', render: r => `$${fmt(r.quantity * r.average_cost)}` },
              { key: 'cur_price', title: '当前价格', render: r => {
                const mkt = priceMap.get(r.asset_code.toUpperCase());
                if (mkt == null) return <span style={{ color: colors.muted, fontSize: 11 }}>估值</span>;
                return `$${fmt(mkt, 4)}`;
              }},
              { key: 'mkt_val', title: '当前市值', render: r => {
                const mkt = priceMap.get(r.asset_code.toUpperCase());
                const val = mkt != null ? r.quantity * mkt : r.quantity * r.average_cost;
                return `$${fmt(val)}`;
              }},
              { key: 'pnl', title: '浮动盈亏', render: r => {
                const mkt = priceMap.get(r.asset_code.toUpperCase());
                if (mkt == null) return '—';
                const pnl = r.quantity * mkt - r.quantity * r.average_cost;
                return <span style={{ color: pnl >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600 }}>{pnl >= 0 ? '+' : ''}{fmt(pnl)}</span>;
              }},
              { key: 'pnl_pct', title: '盈亏%', render: r => {
                const mkt = priceMap.get(r.asset_code.toUpperCase());
                if (mkt == null || r.average_cost === 0) return '—';
                const pct = (mkt - r.average_cost) / r.average_cost * 100;
                return <span style={{ color: pct >= 0 ? '#16a34a' : '#dc2626' }}>{pct >= 0 ? '+' : ''}{fmt(pct, 2)}%</span>;
              }},
              { key: 'snap', title: t('snapshotDate'), render: r => r.snapshot_date },
            ]}
          />
        </div>
      )}

      {/* Transactions tab — shows all categories */}
      {tab === 'transactions' && (
        <div style={styles.card}>
          <div style={{ fontSize: 12, color: colors.muted, marginBottom: 8 }}>
            共 {transactions.length} 条 · 股票 {equityTxns.length} | 现金 {cashTxns.length} | 换汇 {fxTxns.length}
          </div>
          <ProductTable
            emptyText={t('noTransactions')}
            rows={transactions}
            columns={[
              { key: 'date', title: t('tradeDate'), render: r => r.trade_date },
              { key: 'cat', title: '分类', render: r => txCategoryBadge(r) },
              { key: 'type', title: t('txType'), render: r => txTypeBadge(r.tx_type) },
              { key: 'asset', title: t('assetCode'), render: r => r.asset_code ? <strong>{r.asset_code}</strong> : <span style={{ color: colors.muted }}>—</span> },
              { key: 'qty', title: t('quantity'), render: r => r.quantity != null ? fmt(r.quantity, 4) : '—' },
              { key: 'price', title: t('price'), render: r => r.price != null ? fmt(r.price, 4) : '—' },
              { key: 'cur', title: 'Currency', render: r => r.currency },
              { key: 'amount', title: '金额', render: r => {
                // For equity: qty × price. For cash/FX: amount field.
                if (r.tx_category === 'FX' && r.fx_from_currency) {
                  return (
                    <span style={{ fontSize: 12 }}>
                      {r.fx_from_currency} {fmt(Math.abs(r.fx_from_amount || 0))}
                      {' → '}
                      {r.fx_to_currency} {fmt(Math.abs(r.fx_to_amount || 0))}
                    </span>
                  );
                }
                if (r.amount != null) return fmt(r.amount, 2);
                if (r.quantity != null && r.price != null) return `$${fmt(Number(r.quantity) * Number(r.price))}`;
                return '—';
              }},
              { key: 'fee', title: t('feeCol'), render: r => r.fee ? fmt(r.fee, 4) : '—' },
              { key: 'desc', title: '描述', render: r => r.description
                ? <span style={{ fontSize: 11, color: colors.muted }}>{r.description.slice(0, 40)}</span>
                : '—'
              },
              { key: 'src', title: '来源', render: r => <span style={{ fontSize: 11, color: colors.muted }}>{r.source || 'manual'}</span> },
            ]}
          />
        </div>
      )}

      {/* Cash tab — ledger view with balances */}
      {tab === 'cash' && (
        <div>
          {/* V4 Transaction-based balances */}
          <div style={{ ...styles.card, marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>实时余额（基于交易记录计算）</h3>
            {cashBalancesDisplay.length === 0 ? (
              <div style={{ color: colors.muted, fontSize: 13 }}>暂无现金余额数据</div>
            ) : (
              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                {cashBalancesDisplay.map(({ currency, amount }) => (
                  <div key={currency} style={{
                    padding: '12px 20px',
                    borderRadius: 8,
                    border: `1px solid ${amount < 0 ? '#fca5a5' : colors.border}`,
                    background: amount < 0 ? '#fef2f2' : '#f0fdf4',
                    minWidth: 120,
                  }}>
                    <div style={{ fontSize: 12, color: colors.muted }}>{currency}</div>
                    <div style={{
                      fontSize: 20, fontWeight: 700,
                      color: amount < 0 ? '#dc2626' : '#16a34a',
                    }}>
                      {amount < 0 ? '-' : ''}{Math.abs(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    {amount < 0 && <div style={{ fontSize: 10, color: '#dc2626' }}>融资负债</div>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Snapshot-based cash positions (legacy) */}
          <div style={styles.card}>
            <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>快照记录（历史导入）</h3>
            <ProductTable
              emptyText={t('noCash')}
              rows={cashPositions}
              columns={[
                { key: 'id', title: 'ID', render: r => `#${r.id}` },
                { key: 'cur', title: 'Currency', render: r => r.currency },
                { key: 'amt', title: 'Amount', render: r => {
                  const amt = Number(r.amount);
                  return <strong style={{ color: amt < 0 ? '#dc2626' : undefined }}>{fmt(amt, 2)}</strong>;
                }},
                { key: 'snap', title: t('snapshotDate'), render: r => r.snapshot_date },
                { key: 'note', title: t('note'), render: r => r.note || '—' },
                { key: 'at', title: 'Updated', render: r => r.updated_at ? r.updated_at.slice(0, 10) : '—' },
              ]}
            />
          </div>
        </div>
      )}

      {/* FX tab */}
      {tab === 'fx' && (
        <div>
          {/* FX Summary */}
          {fxSummary.length > 0 && (
            <div style={{ ...styles.card, marginBottom: 16 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>换汇汇总</h3>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {fxSummary.map(s => (
                  <div key={`${s.from_currency}-${s.to_currency}`} style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    border: `1px solid ${colors.border}`,
                    background: '#fafafa',
                    minWidth: 200,
                  }}>
                    <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 14 }}>
                      {s.from_currency} → {s.to_currency}
                    </div>
                    <div style={{ fontSize: 12, color: colors.muted }}>
                      卖出: {s.from_currency} {fmt(s.total_from, 0)}
                    </div>
                    <div style={{ fontSize: 12, color: colors.muted }}>
                      买入: {s.to_currency} {fmt(s.total_to, 0)}
                    </div>
                    <div style={{ fontSize: 12, color: colors.muted }}>
                      均价: {fmt(s.avg_rate, 4)}
                    </div>
                    <div style={{ fontSize: 12, color: s.realized_pnl_usd >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600, marginTop: 4 }}>
                      汇兑损益: ${fmt(s.realized_pnl_usd)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* FX transactions list */}
          <div style={styles.card}>
            <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>换汇明细 ({fxTxns.length} 笔)</h3>
            <ProductTable
              emptyText="暂无换汇记录"
              rows={fxTxns}
              columns={[
                { key: 'date', title: '交易日期', render: r => r.trade_date },
                { key: 'from', title: '卖出', render: r => r.fx_from_currency
                  ? `${r.fx_from_currency} ${fmt(Math.abs(r.fx_from_amount || 0), 2)}`
                  : '—'
                },
                { key: 'to', title: '买入', render: r => r.fx_to_currency
                  ? `${r.fx_to_currency} ${fmt(Math.abs(r.fx_to_amount || 0), 2)}`
                  : '—'
                },
                { key: 'rate', title: '汇率', render: r => r.fx_rate ? fmt(r.fx_rate, 4) : '—' },
                { key: 'fee', title: '手续费', render: r => r.fee ? fmt(r.fee, 2) : '—' },
                { key: 'pnl', title: '汇兑损益', render: r => {
                  if (r.fx_pnl == null) return '—';
                  const p = Number(r.fx_pnl);
                  return <span style={{ color: p >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
                    {p >= 0 ? '+' : ''}{fmt(p)}
                  </span>;
                }},
                { key: 'desc', title: '描述', render: r => r.description
                  ? <span style={{ fontSize: 11, color: colors.muted }}>{r.description.slice(0, 50)}</span>
                  : '—'
                },
                { key: 'src', title: '来源', render: r => <span style={{ fontSize: 11, color: colors.muted }}>{r.source || 'manual'}</span> },
              ]}
            />
          </div>
        </div>
      )}

      {/* Import records tab */}
      {tab === 'imports' && (
        <div style={styles.card}>
          <ProductTable
            emptyText={t('noImports')}
            rows={imports}
            columns={[
              { key: 'id', title: 'ID', render: r => `#${r.id}` },
              { key: 'src', title: t('source'), render: r => r.source },
              { key: 'file', title: t('filename'), render: r => r.filename || '—' },
              { key: 'status', title: 'Status', render: r => {
                const c = r.status === 'confirmed' ? '#16a34a' : r.status === 'failed' ? '#dc2626' : '#d97706';
                return <span style={{ color: c, fontWeight: 600, fontSize: 12 }}>{r.status}</span>;
              }},
              { key: 'rows', title: t('rowCount'), render: r => r.row_count },
              { key: 'parsed', title: t('parsedCount'), render: r => r.parsed_count },
              { key: 'confirmed', title: t('confirmedCount'), render: r => r.confirmed_count },
              { key: 'at', title: t('importedAt'), render: r => r.imported_at ? r.imported_at.slice(0, 19).replace('T', ' ') : '—' },
              { key: 'err', title: 'Error', render: r => r.failed_reason ? <span style={{ color: colors.danger, fontSize: 12 }}>{r.failed_reason.slice(0, 60)}</span> : '—' },
            ]}
          />
        </div>
      )}
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  const accountId = Number(context.params?.accountId);
  if (!accountId || isNaN(accountId)) {
    return { redirect: { destination: '/accounts', permanent: false } };
  }

  try {
    const [account, posData, txData, importData, cashData, priceData, cashBalData, fxData] = await Promise.all([
      getAccount(accountId, auth.accessToken),
      getPositions({ accountId, size: 200, accessToken: auth.accessToken }),
      getTransactions({ accountId, size: 200, accessToken: auth.accessToken }),
      getImportBatches({ accountId, accessToken: auth.accessToken }),
      getCashPositions({ accountId, accessToken: auth.accessToken }),
      getPrices({ size: 200, accessToken: auth.accessToken }),
      getCashBalances(accountId, undefined, auth.accessToken).catch(() => null),
      getFxSummary(accountId, auth.accessToken).catch(() => null),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        account,
        positions: posData.items ?? [],
        transactions: txData.items ?? [],
        imports: importData ?? [],
        cashPositions: cashData ?? [],
        cashBalances: cashBalData ?? null,
        fxSummary: fxData?.fx_trades ?? [],
        latestPrices: priceData.items ?? [],
      },
    };
  } catch (error: any) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        account: { id: accountId, fund_id: 0, broker: '—', account_no: '—' },
        positions: [],
        transactions: [],
        imports: [],
        cashPositions: [],
        cashBalances: null,
        fxSummary: [],
        latestPrices: [],
        error: error?.message || 'Failed to load account detail.',
      },
    };
  }
}
