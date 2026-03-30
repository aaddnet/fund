import Link from 'next/link';
import { useMemo, useState } from 'react';
import Layout from '../../components/Layout';
import ProductTable from '../../components/ProductTable';
import {
  Account,
  CashPosition,
  ImportBatch,
  Position,
  Transaction,
  getAccount,
  getCashPositions,
  getImportBatches,
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
  error?: string;
};

export default function Page({ account, positions, transactions, imports, cashPositions, error }: Props) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>('positions');

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'positions', label: t('tabPositions'), count: positions.length },
    { key: 'transactions', label: t('tabTransactions'), count: transactions.length },
    { key: 'imports', label: t('tabImports'), count: imports.length },
    { key: 'cash', label: t('tabCash'), count: cashPositions.length },
  ];

  const totalPositionValue = useMemo(
    () => positions.reduce((sum, p) => sum + Number(p.quantity) * Number(p.average_cost || 0), 0),
    [positions],
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
              <div style={{ fontWeight: 700, fontSize: 18 }}>{positions.length}</div>
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
          <ProductTable
            emptyText={t('noPositions')}
            rows={positions}
            columns={[
              { key: 'asset', title: t('assetCode'), render: r => <strong>{r.asset_code}</strong> },
              { key: 'qty', title: t('quantity'), render: r => fmt(r.quantity, 4) },
              { key: 'avg', title: t('avgCost'), render: r => fmt(r.average_cost, 4) },
              { key: 'cur', title: 'Currency', render: r => r.currency },
              { key: 'val', title: 'Value', render: r => `$${fmt(Number(r.quantity) * Number(r.average_cost || 0))}` },
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
    const [account, posData, txData, importData, cashData] = await Promise.all([
      getAccount(accountId, auth.accessToken),
      getPositions({ accountId, size: 200, accessToken: auth.accessToken }),
      getTransactions({ accountId, size: 200, accessToken: auth.accessToken }),
      getImportBatches({ accountId, accessToken: auth.accessToken }),
      getCashPositions({ accountId, accessToken: auth.accessToken }),
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
        error: error?.message || 'Failed to load account detail.',
      },
    };
  }
}
