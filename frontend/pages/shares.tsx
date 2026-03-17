import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import {
  Client,
  Fund,
  ShareBalance,
  ShareTransaction,
  createShareRedemption,
  createShareSubscription,
  getClients,
  getFunds,
  getShareBalances,
  getShareHistory,
} from '../lib/api';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  shares: ShareTransaction[];
  balances: ShareBalance[];
  funds: Fund[];
  clients: Client[];
  error?: string;
};

type FormMode = 'subscribe' | 'redeem';

export default function Page({ shares, balances, funds, clients, error }: Props) {
  const defaultFundId = String(funds[0]?.id ?? 1);
  const defaultClientId = String(clients[0]?.id ?? 1);
  const [rows, setRows] = useState(shares);
  const [balanceRows, setBalanceRows] = useState(balances);
  const [mode, setMode] = useState<FormMode>('subscribe');
  const [fundId, setFundId] = useState(defaultFundId);
  const [clientId, setClientId] = useState(defaultClientId);
  const [txDate, setTxDate] = useState('2026-06-30');
  const [amountUsd, setAmountUsd] = useState('500');
  const [submitState, setSubmitState] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const selectedBalance = useMemo(
    () => balanceRows.find((item) => item.fund_id === Number(fundId) && item.client_id === Number(clientId)),
    [balanceRows, clientId, fundId],
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setSubmitState('');
    try {
      const payload = {
        fund_id: Number(fundId),
        client_id: Number(clientId),
        tx_date: txDate,
        amount_usd: Number(amountUsd),
      };
      const created = mode === 'subscribe' ? await createShareSubscription(payload) : await createShareRedemption(payload);
      setRows((current) => {
        const merged = [created, ...current.filter((item) => item.id !== created.id)];
        return merged.sort((a, b) => (b.tx_date === a.tx_date ? b.id - a.id : b.tx_date.localeCompare(a.tx_date)));
      });

      const shareDelta = mode === 'subscribe' ? created.shares : -created.shares;
      setBalanceRows((current) => {
        const found = current.find((item) => item.fund_id === created.fund_id && item.client_id === created.client_id);
        if (!found) {
          return [...current, { fund_id: created.fund_id, client_id: created.client_id, share_balance: shareDelta }].sort(
            (a, b) => (a.fund_id === b.fund_id ? a.client_id - b.client_id : a.fund_id - b.fund_id),
          );
        }
        return current
          .map((item) =>
            item.fund_id === created.fund_id && item.client_id === created.client_id
              ? { ...item, share_balance: item.share_balance + shareDelta }
              : item,
          )
          .sort((a, b) => (a.fund_id === b.fund_id ? a.client_id - b.client_id : a.fund_id - b.fund_id));
      });
      setSubmitState(`${mode === 'subscribe' ? 'Subscription' : 'Redemption'} booked successfully for client ${created.client_id}.`);
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : `Failed to ${mode} shares.`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title='Share Transactions' subtitle='Record subscriptions/redemptions against locked NAV dates and review current balances.'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>Backend warning: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Create Share Transaction</h3>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14 }}>
            <FormField label='Transaction Type'>
              <select style={styles.input} value={mode} onChange={(event) => setMode(event.target.value as FormMode)}>
                <option value='subscribe'>Subscribe</option>
                <option value='redeem'>Redeem</option>
              </select>
            </FormField>
            <FormField label='Fund'>
              <select style={styles.input} value={fundId} onChange={(event) => setFundId(event.target.value)}>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>
                    #{fund.id} · {fund.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label='Client'>
              <select style={styles.input} value={clientId} onChange={(event) => setClientId(event.target.value)}>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    #{client.id} · {client.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label='Transaction Date'>
              <input style={styles.input} type='date' value={txDate} onChange={(event) => setTxDate(event.target.value)} />
            </FormField>
            <FormField label='Amount USD'>
              <input style={styles.input} type='number' min='0' step='0.01' value={amountUsd} onChange={(event) => setAmountUsd(event.target.value)} />
            </FormField>
            <div style={{ fontSize: 13, color: colors.muted }}>
              Current client balance: <strong>{formatNumber(selectedBalance?.share_balance ?? 0, 8)}</strong> shares
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
                {submitting ? 'Submitting...' : mode === 'subscribe' ? 'Create Subscription' : 'Create Redemption'}
              </button>
              {submitState ? <span style={{ color: submitState.includes('successfully') ? colors.success : colors.danger }}>{submitState}</span> : null}
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Rules</h3>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>Transactions are allowed only in quarter-end months.</li>
            <li>The transaction date must match an existing locked NAV date.</li>
            <li>The backend calculates shares from amount ÷ NAV at date.</li>
            <li>Redeem validates against the client&apos;s current share balance to prevent over-redemption.</li>
          </ul>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Current Share Balances</h3>
        <ProductTable
          emptyText='No balances found.'
          rows={balanceRows}
          columns={[
            { key: 'fund', title: 'Fund', render: (item) => item.fund_id },
            { key: 'client', title: 'Client', render: (item) => item.client_id },
            { key: 'balance', title: 'Share Balance', render: (item) => formatNumber(item.share_balance, 8) },
          ]}
        />
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

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [shares, balances, fundData, clientData] = await Promise.all([getShareHistory({ accessToken: auth.accessToken }), getShareBalances({ accessToken: auth.accessToken }), getFunds(1, 50, auth.accessToken), getClients({ accessToken: auth.accessToken })]);
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, shares, balances, funds: fundData.items ?? [], clients: clientData.items ?? [] } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, shares: [], balances: [], funds: [], clients: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
