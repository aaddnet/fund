import Link from 'next/link';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { Client, Fund, getClients, getFunds } from '../lib/api';
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
  return (
    <Layout title='Clients' subtitle='Review client master data plus live account/share activity without editing anything.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Client Filters</h3>
          <form method='get' style={{ display: 'grid', gap: 12 }}>
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
              <label style={styles.label}>Client search</label>
              <input name='q' defaultValue={filters.q} style={styles.input} placeholder='Name or email' />
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type='submit' style={styles.buttonPrimary}>Apply Filters</button>
              <Link href='/clients' style={{ ...styles.buttonSecondary, textDecoration: 'none' }}>Reset</Link>
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Operational Summary</h3>
          <p style={{ marginBottom: 8 }}>Matched clients: {total}</p>
          <p style={{ color: colors.muted, marginBottom: 0 }}>
            Each row now includes account coverage, fund coverage, total share balance, and latest activity timestamps pulled from real backend records.
          </p>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Live Client Register</h3>
        <ProductTable
          emptyText='No clients found for the selected filters.'
          rows={rows}
          columns={[
            { key: 'id', title: 'Client ID', render: (item) => item.id },
            { key: 'name', title: 'Name', render: (item) => item.name },
            { key: 'email', title: 'Email', render: (item) => item.email || '—' },
            { key: 'accounts', title: 'Accounts', render: (item) => item.account_count ?? 0 },
            { key: 'funds', title: 'Funds', render: (item) => item.fund_count ?? 0 },
            { key: 'shares', title: 'Share Balance', render: (item) => formatNumber(item.total_share_balance ?? 0, 8) },
            { key: 'txs', title: 'Share Tx', render: (item) => item.share_tx_count ?? 0 },
            { key: 'trade', title: 'Latest Trade', render: (item) => item.latest_trade_date || '—' },
            { key: 'customer', title: 'Customer View', render: (item) => <Link href={`/customers/${item.id}`}>Open</Link> },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: { query: Record<string, string | string[] | undefined> }) {
  const fundId = typeof context.query.fundId === 'string' ? context.query.fundId : '';
  const q = typeof context.query.q === 'string' ? context.query.q : '';

  try {
    const [clientData, fundData] = await Promise.all([
      getClients({ fundId: fundId ? Number(fundId) : undefined, q: q || undefined }),
      getFunds(),
    ]);
    return {
      props: {
        rows: clientData.items ?? [],
        total: clientData.pagination?.total ?? clientData.items?.length ?? 0,
        funds: fundData.items ?? [],
        filters: { fundId, q },
      },
    };
  } catch (error) {
    return {
      props: {
        rows: [],
        total: 0,
        funds: [],
        filters: { fundId, q },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
