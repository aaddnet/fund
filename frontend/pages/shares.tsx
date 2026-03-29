import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import {
  Client,
  Fund,
  NavRecord,
  ShareBalance,
  ShareTransaction,
  createShareRedemption,
  createShareSubscription,
  getClients,
  getFunds,
  getNav,
  getShareBalances,
  getShareHistory,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  shares: ShareTransaction[];
  balances: ShareBalance[];
  funds: Fund[];
  clients: Client[];
  navRecords: NavRecord[];
  error?: string;
};

type FormMode = 'subscribe' | 'redeem';

export default function Page({ shares, balances, funds, clients, navRecords, error }: Props) {
  const { hasPermission } = useAuth();
  const { t } = useI18n();
  const { showToast } = useToast();
  const canWriteShares = hasPermission('shares.write');
  
  const defaultFundId = String(funds[0]?.id ?? 1);
  const defaultClientId = String(clients[0]?.id ?? 1);
  
  const [rows, setRows] = useState(shares);
  const [balanceRows, setBalanceRows] = useState(balances);
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [mode, setMode] = useState<FormMode>('subscribe');
  const [fundId, setFundId] = useState(defaultFundId);
  const [clientId, setClientId] = useState(defaultClientId);
  const lockedNavDates = useMemo(
    () => navRecords.filter((r) => r.is_locked && String(r.fund_id) === fundId).map((r) => r.nav_date).sort().reverse(),
    [navRecords, fundId],
  );
  const [txDate, setTxDate] = useState(() => {
    const first = navRecords.find((r) => r.is_locked);
    return first?.nav_date ?? '';
  });
  const [amountUsd, setAmountUsd] = useState('500');
  const [submitting, setSubmitting] = useState(false);

  const selectedBalance = useMemo(
    () => balanceRows.find((item) => item.fund_id === Number(fundId) && item.client_id === Number(clientId)),
    [balanceRows, clientId, fundId],
  );

  function openModal(newMode: FormMode) {
    setMode(newMode);
    setIsModalOpen(true);
  }

  function closeModal() {
    setIsModalOpen(false);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWriteShares) {
      showToast(t('permissionDenied'), 'error');
      return;
    }
    setSubmitting(true);
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
      showToast(mode === 'subscribe' ? t('subscriptionBooked', { clientId: created.client_id }) : t('redemptionBooked', { clientId: created.client_id }), 'success');
      closeModal();
    } catch (submitError) {
      showToast(submitError instanceof Error ? submitError.message : t('sharesFailed', { mode: mode === 'subscribe' ? t('subscribe') : t('redeem') }), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title={t('sharesTitle')} subtitle={t('sharesSubtitle')} requiredPermission='shares.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16, gap: 10 }}>
        {canWriteShares && (
          <>
            <button style={{...styles.buttonPrimary, backgroundColor: colors.success}} onClick={() => openModal('subscribe')}>+ Subscribe</button>
            <button style={{...styles.buttonPrimary, backgroundColor: colors.danger}} onClick={() => openModal('redeem')}>- Redeem</button>
          </>
        )}
      </div>
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('rules')}</h3>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>{t('sharesRule1')}</li>
            <li>{t('sharesRule2')}</li>
            <li>{t('sharesRule3')}</li>
            <li>{t('sharesRule4')}</li>
          </ul>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('currentShareBalances')}</h3>
          <ProductTable
            emptyText={t('noAccountsFound')}
            rows={balanceRows}
            columns={[
              { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
              { key: 'client', title: t('client'), render: (item) => item.client_id },
              { key: 'balance', title: t('sharesLabel'), render: (item) => formatNumber(item.share_balance, 8) },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('shareLedger')}</h3>
        <ProductTable
          emptyText={t('noShareTransactions')}
          rows={rows}
          columns={[
            { key: 'date', title: t('date'), render: (item) => item.tx_date },
            { key: 'type', title: t('type'), render: (item) => item.tx_type },
            { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
            { key: 'client', title: t('client'), render: (item) => item.client_id },
            { key: 'amount', title: t('amountUsd'), render: (item) => formatNumber(item.amount_usd) },
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.shares, 8) },
            { key: 'nav', title: 'NAV at Date', render: (item) => formatNumber(item.nav_at_date) },
          ]}
        />
      </div>

      <Modal isOpen={isModalOpen} onClose={closeModal} title={mode === 'subscribe' ? t('createSubscription') : t('createRedemption')}>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('fund')}>
            <select style={styles.input} value={fundId} onChange={(event) => setFundId(event.target.value)} disabled={submitting}>
              {funds.map((fund) => (
                <option key={fund.id} value={fund.id}>
                  #{fund.id} · {fund.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t('client')}>
            <select style={styles.input} value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={submitting}>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  #{client.id} · {client.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t('transactionDate')}>
            {lockedNavDates.length > 0 ? (
              <select style={styles.input} value={txDate} onChange={(event) => setTxDate(event.target.value)} disabled={submitting}>
                {lockedNavDates.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            ) : (
              <div style={{ color: colors.danger, fontSize: 13 }}>No locked NAV dates for this fund. Calculate and lock a NAV first.</div>
            )}
          </FormField>
          <FormField label={t('amountUsd')}>
            <input style={styles.input} type='number' min='0' step='0.01' value={amountUsd} onChange={(event) => setAmountUsd(event.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ fontSize: 13, color: colors.muted, marginTop: 4 }}>
            {t('currentClientBalance')}: <strong>{formatNumber(selectedBalance?.share_balance ?? 0, 8)}</strong> {t('sharesLabel')}
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={closeModal} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('submitting') : mode === 'subscribe' ? t('createSubscription') : t('createRedemption')}
            </button>
          </div>
        </form>
      </Modal>

    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [shares, balances, fundData, clientData, navRecords] = await Promise.all([getShareHistory({ accessToken: auth.accessToken }), getShareBalances({ accessToken: auth.accessToken }), getFunds(1, 50, auth.accessToken), getClients({ accessToken: auth.accessToken }), getNav(undefined, auth.accessToken)]);
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, shares, balances, funds: fundData.items ?? [], clients: clientData.items ?? [], navRecords: navRecords ?? [] } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, shares: [], balances: [], funds: [], clients: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
