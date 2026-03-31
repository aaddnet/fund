import Link from 'next/link';
import { useMemo, useState } from 'react';
import Layout from '../../components/Layout';
import ProductTable from '../../components/ProductTable';
import {
  Account,
  AssetPrice,
  CashPosition,
  ImportBatch,
  Position,
  Transaction,
  getAccount,
  getCashPositions,
  getImportBatches,
  getPrices,
  getPositions,
  getTransactions,
} from '../../lib/api';
import { useI18n } from '../../lib/i18n';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, formatNumber, styles } from '../../lib/ui';

type Tab = 'positions' | 'transactions' | 'imports' | 'cash';

type Props = {
  account: Account;
  positions: Position[];
  transactions: Transaction[];
  imports: ImportBatch[];
  cashPositions: CashPosition[];
  latestPrices: AssetPrice[];
  error?: string;
};

export default function Page({ account, positions, transactions, imports, cashPositions, latestPrices, error }: Props) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>('positions');

  // Aggregate positions by (asset_code, currency):
  // - quantity = sum of all snapshots
  // - average_cost = weighted average (total_cost / total_qty)
  // - snapshot_date = latest date among all snapshots
  const aggregatedPositions = useMemo(() => {
    const map = new Map<string, { asset_code: string; currency: string; total_qty: number; total_cost: number; snapshot_date: string }>();
    for (const p of positions) {
      const key = `${p.asset_code}__${p.currency}`;
      const qty = Number(p.quantity);
      const cost = Number(p.average_cost || 0);
      const existing = map.get(key);
      if (existing) {
        existing.total_cost += qty * cost;
        existing.total_qty += qty;
        if (p.snapshot_date > existing.snapshot_date) existing.snapshot_date = p.snapshot_date;
      } else {
        map.set(key, { asset_code: p.asset_code, currency: p.currency, total_qty: qty, total_cost: qty * cost, snapshot_date: p.snapshot_date });
      }
    }
    return Array.from(map.values())
      .filter(r => r.total_qty !== 0)
      .map(r => ({ asset_code: r.asset_code, currency: r.currency, quantity: r.total_qty, average_cost: r.total_qty !== 0 ? r.total_cost / r.total_qty : 0, snapshot_date: r.snapshot_date }))
      .sort((a, b) => a.asset_code.localeCompare(b.asset_code));
  }, [positions]);

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'positions', label: t('tabPositions'), count: aggregatedPositions.length },
    { key: 'transactions', label: t('tabTransactions'), count: transactions.length },
    { key: 'imports', label: t('tabImports'), count: imports.length },
    { key: 'cash', label: t('tabCash'), count: cashPositions.length },
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

  const totalCash = useMemo(
    () => cashPositions.reduce((sum, c) => sum + Number(c.amount), 0),
    [cashPositions],
  );

  const fmt = (n: number | null | undefined, dec = 2) =>
    n == null ? '—' : Number(n).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });

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
              <div style={{ color: colors.muted }}>{t('tabCash')}</div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>${fmt(totalCash)}</div>
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
            同一资产已按代码汇总 · 数量为各快照总和 · 均价为加权平均 · 快照日期为最新记录日期
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

      {/* Transactions tab */}
      {tab === 'transactions' && (
        <div style={styles.card}>
          <ProductTable
            emptyText={t('noTransactions')}
            rows={transactions}
            columns={[
              { key: 'date', title: t('tradeDate'), render: r => r.trade_date },
              { key: 'asset', title: t('assetCode'), render: r => <strong>{r.asset_code}</strong> },
              { key: 'type', title: t('txType'), render: r => {
                const c = r.tx_type === 'BUY' ? '#16a34a' : r.tx_type === 'SELL' ? '#dc2626' : colors.text;
                return <span style={{ color: c, fontWeight: 600, fontSize: 12 }}>{r.tx_type}</span>;
              }},
              { key: 'qty', title: t('quantity'), render: r => fmt(r.quantity, 4) },
              { key: 'price', title: t('price'), render: r => fmt(r.price, 4) },
              { key: 'cur', title: 'Currency', render: r => r.currency },
              { key: 'fee', title: t('feeCol'), render: r => r.fee ? fmt(r.fee, 4) : '—' },
              { key: 'val', title: 'Amount', render: r => `$${fmt(Number(r.quantity) * Number(r.price))}` },
              { key: 'batch', title: t('importBatchId'), render: r => r.import_batch_id ? `#${r.import_batch_id}` : '—' },
            ]}
          />
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

      {/* Cash positions tab */}
      {tab === 'cash' && (
        <div style={styles.card}>
          <ProductTable
            emptyText={t('noCash')}
            rows={cashPositions}
            columns={[
              { key: 'id', title: 'ID', render: r => `#${r.id}` },
              { key: 'cur', title: 'Currency', render: r => r.currency },
              { key: 'amt', title: 'Amount', render: r => <strong>{fmt(r.amount, 2)}</strong> },
              { key: 'snap', title: t('snapshotDate'), render: r => r.snapshot_date },
              { key: 'note', title: t('note'), render: r => r.note || '—' },
              { key: 'at', title: 'Updated', render: r => r.updated_at ? r.updated_at.slice(0, 10) : '—' },
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
    const [account, posData, txData, importData, cashData, priceData] = await Promise.all([
      getAccount(accountId, auth.accessToken),
      getPositions({ accountId, size: 200, accessToken: auth.accessToken }),
      getTransactions({ accountId, size: 200, accessToken: auth.accessToken }),
      getImportBatches({ accountId, accessToken: auth.accessToken }),
      getCashPositions({ accountId, accessToken: auth.accessToken }),
      getPrices({ size: 200, accessToken: auth.accessToken }),
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
        latestPrices: [],
        error: error?.message || 'Failed to load account detail.',
      },
    };
  }
}
