import { useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import { createNav, getFunds, getNav, Fund, NavRecord } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  nav: NavRecord[];
  funds: Fund[];
  error?: string;
};

export default function Page({ nav, funds, error }: Props) {
  const { hasPermission } = useAuth();
  const { t } = useI18n();
  const canWriteNav = hasPermission('nav.write');
  const defaultFundId = String(funds[0]?.id ?? 1);
  const [rows, setRows] = useState(nav);
  const [fundId, setFundId] = useState(defaultFundId);
  const [navDate, setNavDate] = useState('2026-06-30');
  const [submitState, setSubmitState] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  async function handleCreateNav(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWriteNav) {
      setSubmitState(t('permissionDenied'));
      return;
    }
    setSubmitting(true);
    setSubmitState('');
    try {
      const created = await createNav({ fund_id: Number(fundId), nav_date: navDate });
      setRows((current) => {
        const merged = [created, ...current.filter((item) => item.id !== created.id)];
        return merged.sort((a, b) => b.nav_date.localeCompare(a.nav_date));
      });
      setSubmitState(t('navSuccess', { fundId: created.fund_id, date: created.nav_date }));
    } catch (submitError) {
      setSubmitState(submitError instanceof Error ? submitError.message : t('navFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title={t('navTitle')} subtitle={t('navSubtitle')} requiredPermission='nav.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>{t('backendWarning')}: {error}</div> : null}
      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('calculateNav')}</h3>
          <form onSubmit={handleCreateNav} style={{ display: 'grid', gap: 14 }}>
            <FormField label={t('fund')}>
              <select style={styles.input} value={fundId} onChange={(event) => setFundId(event.target.value)} disabled={!canWriteNav}>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>
                    #{fund.id} · {fund.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label={t('navDate')}>
              <input style={styles.input} type='date' value={navDate} onChange={(event) => setNavDate(event.target.value)} disabled={!canWriteNav} />
            </FormField>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <button style={styles.buttonPrimary} disabled={submitting || !canWriteNav} type='submit'>
                {submitting ? t('calculating') : t('calculateNavCta')}
              </button>
              {!canWriteNav ? <span style={{ color: colors.warning }}>{t('readOnlyView')}</span> : null}
              {submitState ? <span style={{ color: submitState.includes('success') || submitState.includes('成功') ? '#16a34a' : '#dc2626' }}>{submitState}</span> : null}
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('guidance')}</h3>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>{t('navGuidance1')}</li>
            <li>{t('navGuidance2')}</li>
            <li>{t('navGuidance3')}</li>
          </ul>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('navLedger')}</h3>
        <ProductTable
          emptyText={t('noNavRecords')}
          rows={rows}
          columns={[
            { key: 'date', title: t('date'), render: (item) => item.nav_date },
            { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
            { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.total_assets_usd) },
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.total_shares, 8) },
            { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.nav_per_share) },
            { key: 'locked', title: t('locked'), render: (item) => (item.is_locked ? t('yes') : t('no')) },
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
    const [nav, fundData] = await Promise.all([getNav(undefined, auth.accessToken), getFunds(1, 50, auth.accessToken)]);
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, nav, funds: fundData.items ?? [] } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, nav: [], funds: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
