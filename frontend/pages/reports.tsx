import Link from 'next/link';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import StatCard from '../components/StatCard';
import { Client, Fund, ReportOverview, getClients, getFunds, getReportOverview } from '../lib/api';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  report: ReportOverview | null;
  funds: Fund[];
  clients: Client[];
  filters: {
    periodType: string;
    periodValue: string;
    fundId: string;
    clientId: string;
  };
  error?: string;
};

export default function Page({ report, funds, clients, filters, error }: Props) {
  return (
    <Layout title='Reports' subtitle='Run practical operational queries by month / quarter / year, with fund and client filters where useful.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>Backend warning: {error}</div> : null}

      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Report Filters</h3>
          <form method='get' style={{ display: 'grid', gap: 12 }}>
            <div>
              <label style={styles.label}>Period Type</label>
              <select name='periodType' defaultValue={filters.periodType} style={styles.input}>
                <option value='month'>Month</option>
                <option value='quarter'>Quarter</option>
                <option value='year'>Year</option>
              </select>
            </div>
            <div>
              <label style={styles.label}>Period Value</label>
              <input name='periodValue' defaultValue={filters.periodValue} style={styles.input} placeholder='2026-Q1 / 2026-03 / 2026' />
            </div>
            <div>
              <label style={styles.label}>Fund</label>
              <select name='fundId' defaultValue={filters.fundId} style={styles.input}>
                <option value=''>All funds</option>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>{`#${fund.id} · ${fund.name}`}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={styles.label}>Client</label>
              <select name='clientId' defaultValue={filters.clientId} style={styles.input}>
                <option value=''>All clients</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{`#${client.id} · ${client.name}`}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type='submit' style={styles.buttonPrimary}>Run Report</button>
              <Link href='/reports' style={{ ...styles.buttonSecondary, textDecoration: 'none' }}>Reset</Link>
            </div>
          </form>
        </div>

        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Report Scope</h3>
          {!report ? (
            <p style={{ color: colors.muted, marginBottom: 0 }}>No report data available.</p>
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              <div><strong>Date range:</strong> {report.filters.date_from} → {report.filters.date_to}</div>
              <div><strong>Fund filter:</strong> {report.filters.fund_id ?? 'All'}</div>
              <div><strong>Client filter:</strong> {report.filters.client_id ?? 'All'}</div>
              <div><strong>Share flow:</strong> {formatNumber(report.summary.net_share_flow_usd)} USD net</div>
            </div>
          )}
        </div>
      </div>

      <div style={{ ...styles.grid3, marginTop: 16 }}>
        <StatCard label='Share Tx' value={String(report?.summary.share_tx_count ?? 0)} />
        <StatCard label='Subscriptions USD' value={formatNumber(report?.summary.subscription_amount_usd ?? 0)} tone='success' />
        <StatCard label='Redemptions USD' value={formatNumber(report?.summary.redemption_amount_usd ?? 0)} tone='warning' />
      </div>
      <div style={{ ...styles.grid3, marginTop: 16 }}>
        <StatCard label='Net Share Flow USD' value={formatNumber(report?.summary.net_share_flow_usd ?? 0)} />
        <StatCard label='NAV Records' value={String(report?.summary.nav_record_count ?? 0)} />
        <StatCard label='Transactions' value={String(report?.summary.transaction_count ?? 0)} />
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Share Flow Detail</h3>
        <ProductTable
          emptyText='No share flow records for this query.'
          rows={report?.share_history ?? []}
          columns={[
            { key: 'date', title: 'Date', render: (item) => item.tx_date },
            { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
            { key: 'client', title: 'Client', render: (item) => item.client_id },
            { key: 'type', title: 'Type', render: (item) => item.tx_type },
            { key: 'amount', title: 'Amount USD', render: (item) => formatNumber(item.amount_usd) },
            { key: 'shares', title: 'Shares', render: (item) => formatNumber(item.shares, 8) },
          ]}
        />
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>NAV Records</h3>
          <ProductTable
            emptyText='No NAV records for this query.'
            rows={report?.nav_records ?? []}
            columns={[
              { key: 'date', title: 'Date', render: (item) => item.nav_date },
              { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
              { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.nav_per_share) },
              { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.total_assets_usd) },
            ]}
          />
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Fee Records</h3>
          <ProductTable
            emptyText='No fee records for this query.'
            rows={report?.fee_records ?? []}
            columns={[
              { key: 'date', title: 'Date', render: (item) => item.fee_date },
              { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
              { key: 'rate', title: 'Fee Rate', render: (item) => formatNumber(item.fee_rate, 4) },
              { key: 'amount', title: 'Amount USD', render: (item) => formatNumber(item.fee_amount_usd) },
            ]}
          />
        </div>
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const periodType = typeof context.query.periodType === 'string' ? context.query.periodType : 'quarter';
  const periodValue = typeof context.query.periodValue === 'string' ? context.query.periodValue : '2026-Q1';
  const fundId = typeof context.query.fundId === 'string' ? context.query.fundId : '';
  const clientId = typeof context.query.clientId === 'string' ? context.query.clientId : '';

  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [report, fundData, clientData] = await Promise.all([
      getReportOverview({ accessToken: auth.accessToken, periodType, periodValue, fundId: fundId ? Number(fundId) : undefined, clientId: clientId ? Number(clientId) : undefined }),
      getFunds(1, 50, auth.accessToken),
      getClients({ accessToken: auth.accessToken }),
    ]);

    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, report, funds: fundData.items ?? [], clients: clientData.items ?? [], filters: { periodType, periodValue, fundId, clientId } } };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, 
        report: null,
        funds: [],
        clients: [],
        filters: { periodType, periodValue, fundId, clientId },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
