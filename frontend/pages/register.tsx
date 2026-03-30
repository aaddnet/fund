import { useMemo, useState } from 'react';
import Layout from '../components/Layout';
import FormField from '../components/FormField';
import { Client, Fund, ShareRegisterEntry, getShareRegister, getClients, getFunds } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  rows: ShareRegisterEntry[];
  funds: Fund[];
  clients: Client[];
  error?: string;
};

const EVENT_COLORS: Record<string, string> = {
  seed: '#2563eb',
  subscription: '#16a34a',
  redemption: '#ea580c',
  fee_deduction: '#dc2626',
};

export default function Page({ rows, funds, clients, error }: Props) {
  const { t } = useI18n();

  const [filterFundId, setFilterFundId] = useState('');
  const [filterClientId, setFilterClientId] = useState('');

  const fundMap = useMemo(() => Object.fromEntries(funds.map(f => [f.id, f.name])), [funds]);
  const clientMap = useMemo(() => Object.fromEntries(clients.map(c => [c.id, c.name])), [clients]);

  const filteredRows = useMemo(() => {
    return rows.filter(r => {
      if (filterFundId && String(r.fund_id) !== filterFundId) return false;
      if (filterClientId && String(r.client_id) !== filterClientId) return false;
      return true;
    });
  }, [rows, filterFundId, filterClientId]);

  const totalSharesAfter = filteredRows.length > 0 ? filteredRows[filteredRows.length - 1].shares_after : null;

  return (
    <Layout title={t('registerTitle')} subtitle={t('registerSubtitle')} requiredPermission="shares.read">
      {error ? <div style={{ ...styles.card, color: colors.danger, marginBottom: 16 }}>{error}</div> : null}

      <div style={{ ...styles.card, marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <FormField label={t('fund')}>
          <select style={{ ...styles.input, width: 160 }} value={filterFundId} onChange={e => setFilterFundId(e.target.value)}>
            <option value="">{t('allFunds')}</option>
            {funds.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('client')}>
          <select style={{ ...styles.input, width: 160 }} value={filterClientId} onChange={e => setFilterClientId(e.target.value)}>
            <option value="">{t('allClients')}</option>
            {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </FormField>
        {totalSharesAfter !== null && (
          <div style={{ marginLeft: 'auto', fontSize: 13, color: colors.muted }}>
            <span style={{ fontWeight: 600, color: colors.text }}>
              {Number(totalSharesAfter).toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 6 })}
            </span>{' '}shares (latest balance shown)
          </div>
        )}
      </div>

      <div style={styles.card}>
        {filteredRows.length === 0 ? (
          <p style={{ color: colors.muted }}>{t('noRegisterEntries')}</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                {[t('date'), t('fund'), t('client'), t('eventType'), t('amountUsd'), t('sharesDelta'), t('sharesAfter'), t('navPerShare'), t('note')]
                  .map((h, i) => <th key={i} style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 600 }}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map(row => {
                const color = EVENT_COLORS[row.event_type] || colors.text;
                const fmt = (n?: number | null, dec = 2) =>
                  n == null ? '—' : Number(n).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
                return (
                  <tr key={row.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                    <td style={{ padding: '8px 10px' }}>{row.event_date}</td>
                    <td style={{ padding: '8px 10px' }}>{fundMap[row.fund_id] ?? `#${row.fund_id}`}</td>
                    <td style={{ padding: '8px 10px' }}>{clientMap[row.client_id] ?? `#${row.client_id}`}</td>
                    <td style={{ padding: '8px 10px' }}>
                      <span style={{
                        background: color + '18',
                        color,
                        borderRadius: 6,
                        padding: '2px 8px',
                        fontWeight: 600,
                        fontSize: 12,
                      }}>
                        {row.event_type}
                      </span>
                    </td>
                    <td style={{ padding: '8px 10px' }}>{fmt(row.amount_usd)}</td>
                    <td style={{ padding: '8px 10px', color: Number(row.shares_delta) >= 0 ? '#16a34a' : '#dc2626' }}>
                      {Number(row.shares_delta) >= 0 ? '+' : ''}{fmt(row.shares_delta, 6)}
                    </td>
                    <td style={{ padding: '8px 10px', fontWeight: 600 }}>{fmt(row.shares_after, 6)}</td>
                    <td style={{ padding: '8px 10px' }}>{fmt(row.nav_per_share, 6)}</td>
                    <td style={{ padding: '8px 10px', color: colors.muted }}>{row.note || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  try {
    const [registerData, fundData, clientData] = await Promise.all([
      getShareRegister({ accessToken: auth.accessToken }),
      getFunds(1, 100, auth.accessToken),
      getClients({ accessToken: auth.accessToken, size: 200 }),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        rows: registerData ?? [],
        funds: fundData.items ?? [],
        clients: clientData.items ?? [],
      },
    };
  } catch (error: any) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        rows: [],
        funds: [],
        clients: [],
        error: error?.message || 'Failed to load share register.',
      },
    };
  }
}
