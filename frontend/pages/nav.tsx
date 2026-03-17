import { useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { createNav, getFunds, getNav, Fund, NavRecord } from '../lib/api';
import { formatNumber, styles } from '../lib/ui';

type Props = {
  nav: NavRecord[];
  funds: Fund[];
  error?: string;
};

export default function Page({ nav, funds, error }: Props) {
  const defaultFundId = String(funds[0]?.id ?? 1);
  const [rows, setRows] = useState(nav);
  const [fundId, setFundId] = useState(defaultFundId);
  const [navDate, setNavDate] = useState('2026-06-30');
  const [submitState, setSubmitState] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  async function handleCreateNav(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setSubmitState('');
    try {
      const created = await createNav({ fund_id: Number(fundId), nav_date: navDate });
      setRows((current) => {
        const merged = [created, ...current.filter((item) => item.id !== created.id)];
        return merged.sort((a, b) => b.nav_date.localeCompare(a.nav_date));
      });
      setSubmitState(`NAV calculated successfully for fund ${created.fund_id} on ${created.nav_date}.`);
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : 'Failed to calculate NAV.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title='NAV Records' subtitle='Calculate fund-level NAV from account-linked positions and snapshot FX/price data.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Calculate NAV</h3>
          <form onSubmit={handleCreateNav} style={{ display: 'grid', gap: 14 }}>
            <FormField label='Fund'>
              <select style={styles.input} value={fundId} onChange={(event) => setFundId(event.target.value)}>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>
                    #{fund.id} · {fund.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label='NAV Date'>
              <input style={styles.input} type='date' value={navDate} onChange={(event) => setNavDate(event.target.value)} />
            </FormField>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
                {submitting ? 'Calculating...' : 'Calculate NAV'}
              </button>
              {submitState ? <span style={{ color: submitState.includes('successfully') ? '#16a34a' : '#dc2626' }}>{submitState}</span> : null}
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Guidance</h3>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>NAV is scoped by <code>fund_id</code> and <code>nav_date</code>.</li>
            <li>Only positions from accounts that belong to the target fund are included.</li>
            <li>Non-USD positions can fall back to average cost with snapshot-date FX conversion when price snapshots are missing.</li>
          </ul>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>NAV Ledger</h3>
        <ProductTable
          emptyText='No NAV records found.'
          rows={rows}
          columns={[
            { key: 'date', title: 'Date', render: (item) => item.nav_date },
            { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
            { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.total_assets_usd) },
            { key: 'shares', title: 'Shares', render: (item) => formatNumber(item.total_shares, 8) },
            { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.nav_per_share) },
            { key: 'locked', title: 'Locked', render: (item) => (item.is_locked ? 'Yes' : 'No') },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const [nav, fundData] = await Promise.all([getNav(), getFunds()]);
    return { props: { nav, funds: fundData.items ?? [] } };
  } catch (error) {
    return { props: { nav: [], funds: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
