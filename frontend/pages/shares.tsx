import { useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { createShareSubscription, getShareHistory, ShareTransaction } from '../lib/api';
import { formatNumber, styles } from '../lib/ui';

type Props = {
  shares: ShareTransaction[];
  error?: string;
};

export default function Page({ shares, error }: Props) {
  const [rows, setRows] = useState(shares);
  const [fundId, setFundId] = useState('1');
  const [clientId, setClientId] = useState('1');
  const [txDate, setTxDate] = useState('2026-06-30');
  const [amountUsd, setAmountUsd] = useState('500');
  const [submitState, setSubmitState] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubscribe(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setSubmitState('');
    try {
      const created = await createShareSubscription({
        fund_id: Number(fundId),
        client_id: Number(clientId),
        tx_date: txDate,
        amount_usd: Number(amountUsd),
      });
      setRows((current) => [created, ...current]);
      setSubmitState(`Subscription booked successfully for client ${created.client_id}.`);
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : 'Failed to create subscription.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title='Share Transactions' subtitle='Record subscriptions against locked NAV dates and review the share ledger.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Create Subscription</h3>
          <form onSubmit={handleSubscribe} style={{ display: 'grid', gap: 14 }}>
            <FormField label='Fund ID'>
              <input style={styles.input} value={fundId} onChange={(event) => setFundId(event.target.value)} />
            </FormField>
            <FormField label='Client ID'>
              <input style={styles.input} value={clientId} onChange={(event) => setClientId(event.target.value)} />
            </FormField>
            <FormField label='Transaction Date'>
              <input style={styles.input} type='date' value={txDate} onChange={(event) => setTxDate(event.target.value)} />
            </FormField>
            <FormField label='Amount USD'>
              <input style={styles.input} type='number' value={amountUsd} onChange={(event) => setAmountUsd(event.target.value)} />
            </FormField>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
                {submitting ? 'Submitting...' : 'Create Subscription'}
              </button>
              {submitState ? <span style={{ color: submitState.includes('successfully') ? '#16a34a' : '#dc2626' }}>{submitState}</span> : null}
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Rules</h3>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>Transactions are allowed only in quarter-end months.</li>
            <li>The transaction date must match an existing locked NAV date.</li>
            <li>The backend calculates shares from amount ÷ NAV at date.</li>
          </ul>
        </div>
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Share Ledger</h3>
        <ProductTable
          emptyText='No share transactions found.'
          rows={rows}
          columns={[
            { key: 'date', title: 'Date', render: (item) => item.tx_date },
            { key: 'type', title: 'Type', render: (item) => item.tx_type },
            { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
            { key: 'client', title: 'Client', render: (item) => item.client_id },
            { key: 'amount', title: 'Amount USD', render: (item) => formatNumber(item.amount_usd) },
            { key: 'shares', title: 'Shares', render: (item) => formatNumber(item.shares, 8) },
            { key: 'nav', title: 'NAV at Date', render: (item) => formatNumber(item.nav_at_date) },
          ]}
        />
      </div>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    return { props: { shares: await getShareHistory() } };
  } catch (error) {
    return { props: { shares: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
