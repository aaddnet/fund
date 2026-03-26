import Link from 'next/link';
import Layout from '../../components/Layout';
import ProductTable from '../../components/ProductTable';
import { Client, CustomerView, getClients, getCustomerView } from '../../lib/api';
import { useI18n } from '../../lib/i18n';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, formatNumber, styles } from '../../lib/ui';

type Props = {
  customer?: CustomerView | null;
  clients: Client[];
  selectedClientId: number | null;
  error?: string;
};

export default function Page({ customer, clients, selectedClientId, error }: Props) {
  const { t } = useI18n();

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
            { key: 'client', title: t('client'), render: (item) => item.client_id },
            { key: 'balance', title: t('sharesLabel'), render: (item) => formatNumber(item.share_balance, 8) },
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
    const customer = resolvedClientId ? await getCustomerView(resolvedClientId, auth.accessToken) : null;

    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, customer, clients, selectedClientId: resolvedClientId } };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        customer: null,
        clients: [],
        selectedClientId,
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
