import Link from 'next/link';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { Client, Fund, getClients, getFunds } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  rows: Client[];
  total: number;
  funds: Fund[];
  filters: {
    fundId: string;
    q: string;
  };
  error?: string;
};

export default function Page({ rows, total, funds, filters, error }: Props) {
  const { t } = useI18n();

  return (
    <Layout title={t('clientsTitle')} subtitle={t('clientsSubtitle')} requiredPermission='clients.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('clientFilters')}</h3>
          <form method='get' style={{ display: 'grid', gap: 12 }}>
            <div>
              <label style={styles.label}>{t('fund')}</label>
              <select name='fundId' defaultValue={filters.fundId} style={styles.input}>
                <option value=''>{t('allFunds')}</option>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>{`#${fund.id} · ${fund.name}`}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={styles.label}>{t('clientSearch')}</label>
              <input name='q' defaultValue={filters.q} style={styles.input} placeholder='Name or email' />
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type='submit' style={styles.buttonPrimary}>{t('applyFilters')}</button>
              <Link href='/clients' style={{ ...styles.buttonSecondary, textDecoration: 'none' }}>{t('reset')}</Link>
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('summary')}</h3>
          <p style={{ marginBottom: 8 }}>{t('matchedClients')}: {total}</p>
          <p style={{ color: colors.muted, marginBottom: 0 }}>{t('clientSummary')}</p>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('liveClientRegister')}</h3>
        <ProductTable
          emptyText={t('noClientsForFilter')}
          rows={rows}
          columns={[
            { key: 'id', title: 'Client ID', render: (item) => item.id },
            { key: 'name', title: t('customerName'), render: (item) => item.name },
            { key: 'email', title: t('email'), render: (item) => item.email || t('notAvailable') },
            { key: 'accounts', title: t('accountsCount'), render: (item) => item.account_count ?? 0 },
            { key: 'funds', title: t('fundsLabel'), render: (item) => item.fund_count ?? 0 },
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.total_share_balance ?? 0, 8) },
            { key: 'txs', title: t('shareTransactionsLabel'), render: (item) => item.share_tx_count ?? 0 },
            { key: 'trade', title: t('latestTrade'), render: (item) => item.latest_trade_date || t('notAvailable') },
            { key: 'customer', title: t('customerView'), render: (item) => <Link href={`/customers/${item.id}`}>{t('customerOpen')}</Link> },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const fundId = typeof context.query.fundId === 'string' ? context.query.fundId : '';
  const q = typeof context.query.q === 'string' ? context.query.q : '';

  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [clientData, fundData] = await Promise.all([
      getClients({ accessToken: auth.accessToken, fundId: fundId ? Number(fundId) : undefined, q: q || undefined }),
      getFunds(1, 50, auth.accessToken),
    ]);
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: clientData.items ?? [],
        total: clientData.pagination?.total ?? clientData.items?.length ?? 0,
        funds: fundData.items ?? [],
        filters: { fundId, q },
      },
    };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: [],
        total: 0,
        funds: [],
        filters: { fundId, q },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
