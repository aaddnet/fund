import Link from 'next/link';
import { useMemo } from 'react';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { Account, Client, Fund, getAccounts, getClients, getFunds } from '../lib/api';
import { colors, styles } from '../lib/ui';

type Props = {
  rows: Account[];
  total: number;
  funds: Fund[];
  clients: Client[];
  filters: {
    fundId: string;
    clientId: string;
    broker: string;
    q: string;
  };
  error?: string;
};

export default function Page({ rows, total, funds, clients, filters, error }: Props) {
  const activeFilterCount = useMemo(() => [filters.fundId, filters.clientId, filters.broker, filters.q].filter(Boolean).length, [filters]);

  return (
    <Layout title='Accounts' subtitle='Use real account, fund, client, position, and transaction data for read-only operational review.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>Backend warning: {error}</div> : null}

      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Account Filters</h3>
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
              <label style={styles.label}>Client</label>
              <select name='clientId' defaultValue={filters.clientId} style={styles.input}>
                <option value=''>All clients</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{`#${client.id} · ${client.name}`}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={styles.label}>Broker contains</label>
              <input name='broker' defaultValue={filters.broker} style={styles.input} placeholder='IB / HK Broker / ...' />
            </div>
            <div>
              <label style={styles.label}>Account / broker search</label>
              <input name='q' defaultValue={filters.q} style={styles.input} placeholder='ACC-001 / IB / ...' />
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type='submit' style={styles.buttonPrimary}>Apply Filters</button>
              <Link href='/accounts' style={{ ...styles.buttonSecondary, textDecoration: 'none' }}>Reset</Link>
            </div>
          </form>
        </div>

        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Operational Summary</h3>
          <p style={{ marginBottom: 8 }}>Matched accounts: {total}</p>
          <p style={{ marginBottom: 8 }}>Active filters: {activeFilterCount}</p>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>Latest snapshot date helps locate stale custody data.</li>
            <li>Latest trade date makes dormant accounts obvious.</li>
            <li>Fund/client names come from live backend joins instead of draft labels.</li>
          </ul>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Live Account Register</h3>
        <ProductTable
          emptyText='No accounts found for the selected filters.'
          rows={rows}
          columns={[
            { key: 'id', title: 'Account ID', render: (item) => item.id },
            { key: 'fund', title: 'Fund', render: (item) => item.fund_name || `Fund #${item.fund_id}` },
            { key: 'client', title: 'Client', render: (item) => item.client_name || (item.client_id ? `Client #${item.client_id}` : '—') },
            { key: 'broker', title: 'Broker', render: (item) => item.broker },
            { key: 'account', title: 'Account No', render: (item) => item.account_no },
            { key: 'positions', title: 'Positions', render: (item) => item.position_count },
            { key: 'transactions', title: 'Transactions', render: (item) => item.transaction_count },
            { key: 'trade', title: 'Latest Trade', render: (item) => item.latest_trade_date || '—' },
            { key: 'snapshot', title: 'Latest Snapshot', render: (item) => item.latest_snapshot_date || '—' },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: { query: Record<string, string | string[] | undefined> }) {
  const fundId = typeof context.query.fundId === 'string' ? context.query.fundId : '';
  const clientId = typeof context.query.clientId === 'string' ? context.query.clientId : '';
  const broker = typeof context.query.broker === 'string' ? context.query.broker : '';
  const q = typeof context.query.q === 'string' ? context.query.q : '';

  try {
    const [accountData, fundData, clientData] = await Promise.all([
      getAccounts({ fundId: fundId ? Number(fundId) : undefined, clientId: clientId ? Number(clientId) : undefined, broker: broker || undefined, q: q || undefined }),
      getFunds(),
      getClients(),
    ]);

    return {
      props: {
        rows: accountData.items ?? [],
        total: accountData.pagination?.total ?? accountData.items?.length ?? 0,
        funds: fundData.items ?? [],
        clients: clientData.items ?? [],
        filters: { fundId, clientId, broker, q },
      },
    };
  } catch (error) {
    return {
      props: {
        rows: [],
        total: 0,
        funds: [],
        clients: [],
        filters: { fundId, clientId, broker, q },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
