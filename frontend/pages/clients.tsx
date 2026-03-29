import Link from 'next/link';
import { useState } from 'react';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { Client, Fund, getClients, getFunds, createClient, updateClient } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
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
  const { t } = useI18n();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canWrite = hasPermission('clients.write');

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function openCreate() {
    setName('');
    setEmail('');
    setIsCreateOpen(true);
  }

  function openEdit(client: Client) {
    setName(client.name);
    setEmail(client.email || '');
    setEditingClient(client);
  }

  function closeModals() {
    setIsCreateOpen(false);
    setEditingClient(null);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setSubmitting(true);
    try {
      await createClient({ name, email: email || null });
      showToast('Client created successfully', 'success');
      window.location.reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to create client', 'error');
      setSubmitting(false);
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite || !editingClient) return;
    setSubmitting(true);
    try {
      await updateClient(editingClient.id, { name, email: email || null });
      showToast('Client updated successfully', 'success');
      window.location.reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update client', 'error');
      setSubmitting(false);
    }
  }

  return (
    <Layout title={t('clientsTitle')} subtitle={t('clientsSubtitle')} requiredPermission='clients.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}
      
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        {canWrite && (
          <button style={styles.buttonPrimary} onClick={openCreate}>+ Create Client</button>
        )}
      </div>

      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('clientFilters')}</h3>
          <form method='get' style={{ display: 'grid', gap: 12 }}>
            <div>
              <label style={styles.label}>{t('fund')}</label>
              <select name='fundId' defaultValue={filters.fundId} style={styles.input}>
                <option value=''>{t('allFunds')}</option>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>{`#${fund.id} · ${fund.name}`}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={styles.label}>{t('clientSearch')}</label>
              <input name='q' defaultValue={filters.q} style={styles.input} placeholder='Name or email' />
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type='submit' style={styles.buttonPrimary}>{t('applyFilters')}</button>
              <Link href='/clients' style={{ ...styles.buttonSecondary, textDecoration: 'none' }}>{t('reset')}</Link>
            </div>
          </form>
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('summary')}</h3>
          <p style={{ marginBottom: 8 }}>{t('matchedClients')}: {total}</p>
          <p style={{ color: colors.muted, marginBottom: 0 }}>{t('clientSummary')}</p>
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('liveClientRegister')}</h3>
        <ProductTable
          emptyText={t('noClientsForFilter')}
          rows={rows}
          columns={[
            { key: 'id', title: 'Client ID', render: (item) => item.id },
            { key: 'name', title: t('customerName'), render: (item) => item.name },
            { key: 'email', title: t('email'), render: (item) => item.email || t('notAvailable') },
            { key: 'funds', title: t('fundsLabel'), render: (item) => item.fund_count ?? 0 },
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.total_share_balance ?? 0, 8) },
            { key: 'holdingValue', title: 'Holding Value (USD)', render: (item) => item.total_holding_value_usd != null && item.total_holding_value_usd > 0 ? `$${item.total_holding_value_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : t('notAvailable') },
            { key: 'txs', title: t('shareTransactionsLabel'), render: (item) => item.share_tx_count ?? 0 },
            { key: 'trade', title: t('latestTrade'), render: (item) => item.latest_trade_date || t('notAvailable') },
            { key: 'customer', title: t('customerView'), render: (item) => <Link href={`/customers/${item.id}`}>{t('customerOpen')}</Link> },
            ...(canWrite ? [{
              key: 'actions', title: 'Actions', render: (item: Client) => (
                <button
                  style={{ ...styles.buttonSecondary, padding: '4px 8px', fontSize: 12 }}
                  onClick={() => openEdit(item)}
                >
                  Edit
                </button>
              )
            }] : [])
          ]}
        />
      </div>

      <Modal isOpen={isCreateOpen} onClose={closeModals} title="Create Client">
        <form onSubmit={handleCreate} style={{ display: 'grid', gap: 14 }}>
          <FormField label="Name">
            <input required style={styles.input} value={name} onChange={e => setName(e.target.value)} disabled={submitting} />
          </FormField>
          <FormField label="Email">
            <input style={styles.input} type="email" value={email} onChange={e => setEmail(e.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type="submit">
              {submitting ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={!!editingClient} onClose={closeModals} title="Edit Client">
        <form onSubmit={handleEdit} style={{ display: 'grid', gap: 14 }}>
          <FormField label="Name">
            <input required style={styles.input} value={name} onChange={e => setName(e.target.value)} disabled={submitting} />
          </FormField>
          <FormField label="Email">
            <input style={styles.input} type="email" value={email} onChange={e => setEmail(e.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
            <button type="button" onClick={closeModals} style={styles.buttonSecondary} disabled={submitting}>Cancel</button>
            <button style={styles.buttonPrimary} disabled={submitting} type="submit">
              {submitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </Modal>

    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const fundId = typeof context.query.fundId === 'string' ? context.query.fundId : '';
  const q = typeof context.query.q === 'string' ? context.query.q : '';

  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [clientData, fundData] = await Promise.all([
      getClients({ accessToken: auth.accessToken, fundId: fundId ? Number(fundId) : undefined, q: q || undefined }),
      getFunds(1, 50, auth.accessToken),
    ]);
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: clientData.items ?? [],
        total: clientData.pagination?.total ?? clientData.items?.length ?? 0,
        funds: fundData.items ?? [],
        filters: { fundId, q },
      },
    };
  } catch (error) {
    return {
      props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale,
        rows: [],
        total: 0,
        funds: [],
        filters: { fundId, q },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
