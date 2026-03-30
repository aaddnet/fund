import { useMemo, useState } from 'react';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { Fund, NavRecord, getFunds, getNav, createFund, updateFund } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  rows: Fund[];
  total: number;
  navRecords: NavRecord[];
  error?: string;
};

const CURRENCIES = ['USD', 'HKD', 'EUR', 'GBP', 'SGD', 'CNY', 'JPY'];

export default function Page({ rows, total, navRecords, error }: Props) {
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canWrite = hasPermission('clients.write');

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingFund, setEditingFund] = useState<Fund | null>(null);
  const [name, setName] = useState('');
  const [baseCurrency, setBaseCurrency] = useState('USD');
  const [totalShares, setTotalShares] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Latest locked NAV per fund: fund_id → NavRecord
  const latestNavByFund = useMemo(() => {
    const map: Record<number, NavRecord> = {};
    [...navRecords]
      .filter(r => r.is_locked)
      .sort((a, b) => b.nav_date.localeCompare(a.nav_date))
      .forEach(r => {
        if (!(r.fund_id in map)) map[r.fund_id] = r;
      });
    return map;
  }, [navRecords]);

  function openCreate() {
    setName('');
    setBaseCurrency('USD');
    setTotalShares('');
    setIsCreateOpen(true);
  }

  function openEdit(fund: Fund) {
    setName(fund.name);
    setBaseCurrency(fund.base_currency);
    setTotalShares(fund.total_shares != null && Number(fund.total_shares) > 0 ? String(fund.total_shares) : '');
    setEditingFund(fund);
  }

  function closeModals() {
    setIsCreateOpen(false);
    setEditingFund(null);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setSubmitting(true);
    try {
      await createFund({ name, base_currency: baseCurrency, total_shares: totalShares ? Number(totalShares) : undefined });
      showToast('Fund created successfully', 'success');
      window.location.reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to create fund', 'error');
      setSubmitting(false);
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite || !editingFund) return;
    setSubmitting(true);
    try {
      await updateFund(editingFund.id, { name, base_currency: baseCurrency, total_shares: totalShares ? Number(totalShares) : undefined });
      showToast('Fund updated successfully', 'success');
      window.location.reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update fund', 'error');
      setSubmitting(false);
    }
  }

  const fmtUsd = (n: number) =>
    n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <Layout title={t('funds')} subtitle='Manage investment funds' requiredPermission='nav.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ color: colors.muted, fontSize: 14 }}>
          {total} {t('funds').toLowerCase()} registered
        </div>
        {canWrite && (
          <button style={styles.buttonPrimary} onClick={openCreate}>+ Create Fund</button>
        )}
      </div>

      <div style={styles.card}>
        <h3 style={{ marginTop: 0 }}>Fund Register</h3>
        <ProductTable
          emptyText='No funds found. Create a fund to get started.'
          rows={rows}
          columns={[
            { key: 'id', title: 'Fund ID', render: (item) => `#${item.id}` },
            { key: 'name', title: 'Name', render: (item) => <strong>{item.name}</strong> },
            { key: 'currency', title: 'Base Currency', render: (item) => item.base_currency },
            { key: 'status', title: t('fundStatus'), render: (item) => {
              const s = item.status || 'draft';
              const color = s === 'active' ? '#16a34a' : s === 'closed' ? '#6b7280' : '#d97706';
              return <span style={{ color, fontWeight: 600, fontSize: 12 }}>{t(s as any)}</span>;
            }},
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.total_shares ?? 0, 6) },
            { key: 'navPerShare', title: t('navPerShare'), render: (item) => {
              const nav = latestNavByFund[item.id];
              if (!nav) return <span style={{ color: colors.muted }}>—</span>;
              return (
                <span title={`NAV date: ${nav.nav_date}`}>
                  {formatNumber(nav.nav_per_share, 6)}
                </span>
              );
            }},
            { key: 'totalValue', title: t('totalMarketValue'), render: (item) => {
              const nav = latestNavByFund[item.id];
              if (!nav || !item.total_shares) return <span style={{ color: colors.muted }}>—</span>;
              const value = Number(item.total_shares) * Number(nav.nav_per_share);
              return <strong>${fmtUsd(value)}</strong>;
            }},
            { key: 'navDate', title: 'Latest NAV Date', render: (item) => {
              const nav = latestNavByFund[item.id];
              return nav ? <span style={{ color: colors.muted, fontSize: 12 }}>{nav.nav_date}</span> : '—';
            }},
            { key: 'created', title: 'Created', render: (item) => item.created_at ? item.created_at.slice(0, 10) : '—' },
            ...(canWrite ? [{
              key: 'actions',
              title: 'Actions',
              render: (item: Fund) => (
                <button
                  style={{ ...styles.buttonSecondary, padding: '4px 8px', fontSize: 12 }}
                  onClick={() => openEdit(item)}
                >
                  Edit
                </button>
              ),
            }] : []),
          ]}
        />
      </div>

      <Modal isOpen={isCreateOpen} onClose={closeModals} title='Create Fund'>
        <form onSubmit={handleCreate} style={{ display: 'grid', gap: 14 }}>
          <FormField label='Fund Name'>
            <input
              required
              style={styles.input}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder='e.g. Alpha Growth Fund'
              disabled={submitting}
            />
          </FormField>
          <FormField label='Base Currency'>
            <select style={styles.input} value={baseCurrency} onChange={(e) => setBaseCurrency(e.target.value)} disabled={submitting}>
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </FormField>
          <FormField label={t('sharesLabel')}>
            <input
              type='number'
              min='0'
              step='any'
              style={styles.input}
              value={totalShares}
              onChange={(e) => setTotalShares(e.target.value)}
              placeholder='e.g. 1000000'
              disabled={submitting}
            />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type='button' onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>{t('cancel')}</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('creating') : 'Create Fund'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={!!editingFund} onClose={closeModals} title='Edit Fund'>
        <form onSubmit={handleEdit} style={{ display: 'grid', gap: 14 }}>
          <FormField label='Fund Name'>
            <input
              required
              style={styles.input}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={submitting}
            />
          </FormField>
          <FormField label='Base Currency'>
            <select style={styles.input} value={baseCurrency} onChange={(e) => setBaseCurrency(e.target.value)} disabled={submitting}>
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </FormField>
          <FormField label={t('sharesLabel')}>
            <input
              type='number'
              min='0'
              step='any'
              style={styles.input}
              value={totalShares}
              onChange={(e) => setTotalShares(e.target.value)}
              placeholder='e.g. 1000000'
              disabled={submitting}
            />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type='button' onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>{t('cancel')}</button>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('saving') : 'Save Changes'}
            </button>
          </div>
        </form>
      </Modal>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  try {
    const [fundData, navData] = await Promise.all([
      getFunds(1, 100, auth.accessToken),
      getNav(undefined, auth.accessToken),
    ]);
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        rows: fundData.items ?? [],
        total: fundData.pagination?.total ?? fundData.items?.length ?? 0,
        navRecords: navData ?? [],
      },
    };
  } catch (error) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        rows: [],
        total: 0,
        navRecords: [],
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
