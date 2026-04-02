import { useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { createNav, deleteNav, getNav, NavRecord } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  nav: NavRecord[];
  error?: string;
};

export default function Page({ nav, error }: Props) {
  const { hasPermission } = useAuth();
  const { t } = useI18n();
  const { showToast } = useToast();
  const canWriteNav = hasPermission('nav.write');

  const [rows, setRows] = useState(nav);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [navDate, setNavDate] = useState('2026-06-30');
  const [forceRecalc, setForceRecalc] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleDeleteNav(navId: number) {
    if (!canWriteNav) return;
    if (!confirm('Delete this NAV record? This will also delete the associated asset snapshots.')) return;
    try {
      await deleteNav(navId);
      setRows(current => current.filter(r => r.id !== navId));
      showToast('NAV record deleted.', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to delete NAV record.', 'error');
    }
  }

  async function handleCreateNav(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWriteNav) { showToast(t('permissionDenied'), 'error'); return; }
    setSubmitting(true);
    try {
      const created = await createNav({ nav_date: navDate, force: forceRecalc });
      setRows((current) => {
        const merged = [created, ...current.filter((item) => item.id !== created.id)];
        return merged.sort((a, b) => b.nav_date.localeCompare(a.nav_date));
      });
      showToast(t('navSuccess', { fundId: '', date: created.nav_date }), 'success');
      setIsModalOpen(false);
    } catch (submitError) {
      showToast(submitError instanceof Error ? submitError.message : t('navFailed'), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title="组合价值" subtitle="Portfolio Value" requiredPermission='nav.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>{t('backendWarning')}: {error}</div> : null}

      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 16 }}>
        {canWriteNav && (
          <button style={styles.buttonPrimary} onClick={() => setIsModalOpen(true)}>+ Calculate NAV</button>
        )}
      </div>
          <div style={styles.grid2}>
            <div style={{ ...styles.card, gridColumn: '1 / -1' }}>
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
                { key: 'assets', title: 'Assets USD', render: (item) => item.total_assets_usd === 0 ? '— (no positions)' : formatNumber(item.total_assets_usd) },
                { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.total_shares, 8) },
                { key: 'nav', title: 'NAV / Share', render: (item) => item.nav_per_share === 0 ? '— (no positions)' : formatNumber(item.nav_per_share) },
                { key: 'locked', title: t('locked'), render: (item) => (item.is_locked ? t('yes') : t('no')) },
                ...(canWriteNav ? [{
                  key: 'del', title: '', render: (item: NavRecord) => (
                    <button style={{ ...styles.buttonSecondary, padding: '4px 8px', fontSize: 12, color: colors.danger, borderColor: colors.danger }} onClick={() => handleDeleteNav(item.id)}>
                      Delete
                    </button>
                  ),
                }] : []),
              ]}
            />
          </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={t('calculateNavCta')}>
        <form onSubmit={handleCreateNav} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('navDate')}>
            <input style={styles.input} type='date' value={navDate} onChange={(event) => setNavDate(event.target.value)} disabled={submitting} />
          </FormField>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
            <input type='checkbox' checked={forceRecalc} onChange={e => setForceRecalc(e.target.checked)} disabled={submitting} />
            {t('forceRecalc')}
          </label>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={() => setIsModalOpen(false)} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('calculating') : t('calculateNavCta')}
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
    const nav = await getNav(auth.accessToken);
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, nav } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, nav: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
