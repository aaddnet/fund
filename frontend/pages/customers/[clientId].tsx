import Link from 'next/link';
import { useMemo } from 'react';
import Layout from '../../components/Layout';
import ProductTable from '../../components/ProductTable';
import { CapitalAccount, Client, CustomerView, getClientCapitalAccounts, getClients, getCustomerView } from '../../lib/api';
import { useI18n } from '../../lib/i18n';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, formatNumber, styles } from '../../lib/ui';

type Props = {
  customer?: CustomerView | null;
  clients: Client[];
  selectedClientId: number | null;
  capitalAccounts?: CapitalAccount[];
  error?: string;
};

export default function Page({ customer, clients, selectedClientId, capitalAccounts = [], error }: Props) {
  const { t } = useI18n();

  // Latest locked NAV per share per fund, for computing holding value
  const latestNavPerFund = useMemo(() => {
    const map: Record<number, number> = {};
    [...(customer?.nav_history ?? [])]
      .filter(r => r.is_locked)
      .sort((a, b) => b.nav_date.localeCompare(a.nav_date))
      .forEach(r => {
        if (!(r.fund_id in map)) map[r.fund_id] = r.nav_per_share;
      });
    return map;
  }, [customer]);

  return (
    <Layout title={t('customerTitle')} subtitle={t('customerSubtitle')} requiredPermission='customer.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('switchCustomer')}</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            {clients.map((client) => (
              <Link key={client.id} href={`/customers/${client.id}`} style={{ color: client.id === selectedClientId ? colors.primary : colors.text, fontWeight: client.id === selectedClientId ? 700 : 500 }}>
                {`#${client.id} · ${client.name}`}
              </Link>
            ))}
          </div>
        </div>

        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('customerSummaryTitle')}</h3>
          {!customer ? (
            <p style={{ color: colors.muted, marginBottom: 0 }}>{t('noCustomerSelected')}</p>
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              <div><strong>{t('customerName')}:</strong> {customer.client.name}</div>
              <div><strong>{t('email')}:</strong> {customer.client.email || t('notAvailable')}</div>
              <div><strong>{t('accountsCount')}:</strong> {customer.accounts.length}</div>
              <div><strong>{t('fundsLabel')}:</strong> {customer.client.fund_count ?? customer.share_balances.length}</div>
              <div><strong>{t('shareTransactionsLabel')}:</strong> {customer.share_history.length}</div>
            </div>
          )}
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('currentShareBalances')}</h3>
        <ProductTable
          emptyText={t('noAccountsFound')}
          rows={customer?.share_balances ?? []}
          columns={[
            { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
            { key: 'balance', title: t('sharesLabel'), render: (item) => formatNumber(item.share_balance, 8) },
            { key: 'value', title: 'Holding Value (USD)', render: (item) => {
              const nav = latestNavPerFund[item.fund_id];
              if (!nav) return t('notAvailable');
              const value = item.share_balance * nav;
              return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }},
          ]}
        />
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('shareTransactionHistory')}</h3>
        <ProductTable
          emptyText={t('noShareTransactions')}
          rows={customer?.share_history ?? []}
          columns={[
            { key: 'date', title: t('date'), render: (item) => item.tx_date },
            { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
            { key: 'type', title: t('type'), render: (item) => item.tx_type },
            { key: 'amount', title: t('amountUsd'), render: (item) => formatNumber(item.amount_usd) },
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.shares, 8) },
            { key: 'nav', title: 'NAV at Date', render: (item) => formatNumber(item.nav_at_date) },
          ]}
        />
      </div>

      {capitalAccounts.length > 0 && (
        <div style={{ ...styles.card, marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>{t('capitalAccount')}</h3>
          <ProductTable
            emptyText="No capital account data."
            rows={capitalAccounts}
            columns={[
              { key: 'fund', title: t('fund'), render: (item) => `Fund #${item.fund_id}` },
              { key: 'invested', title: t('totalInvested'), render: (item) => `$${formatNumber(item.total_invested_usd)}` },
              { key: 'redeemed', title: 'Total Redeemed', render: (item) => `$${formatNumber(item.total_redeemed_usd)}` },
              { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.current_shares, 6) },
              { key: 'avgNav', title: t('avgCostNav'), render: (item) => item.avg_cost_nav != null ? formatNumber(item.avg_cost_nav, 6) : t('notAvailable') },
              { key: 'pnl', title: t('unrealizedPnl'), render: (item) => {
                if (item.unrealized_pnl_usd == null) return t('notAvailable');
                const v = item.unrealized_pnl_usd;
                const color = v >= 0 ? '#16a34a' : '#dc2626';
                return <span style={{ color, fontWeight: 600 }}>${formatNumber(v)}</span>;
              }},
              { key: 'updated', title: 'Last Updated', render: (item) => item.last_updated_date || t('notAvailable') },
            ]}
          />
        </div>
      )}

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('relevantNavHistory')}</h3>
        <ProductTable
          emptyText={t('noNavForQuery')}
          rows={customer?.nav_history ?? []}
          columns={[
            { key: 'date', title: t('navDate'), render: (item) => item.nav_date },
            { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
            { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.nav_per_share) },
            { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.total_assets_usd) },
            { key: 'locked', title: t('locked'), render: (item) => (item.is_locked ? t('yes') : t('no')) },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const clientIdText = typeof context.params?.clientId === 'string' ? context.params.clientId : '';
  const selectedClientId = clientIdText ? Number(clientIdText) : null;

  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const clientData = await getClients({ accessToken: auth.accessToken });
    const clients = clientData.items ?? [];
    const resolvedClientId = selectedClientId ?? clients[0]?.id ?? null;
    const [customer, capitalAccounts] = await Promise.all([
      resolvedClientId ? getCustomerView(resolvedClientId, auth.accessToken) : Promise.resolve(null),
      resolvedClientId ? getClientCapitalAccounts(resolvedClientId, auth.accessToken).catch(() => []) : Promise.resolve([]),
    ]);

    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, customer, clients, selectedClientId: resolvedClientId, capitalAccounts } };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        customer: null,
        clients: [],
        selectedClientId,
        capitalAccounts: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
