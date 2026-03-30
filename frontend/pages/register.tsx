import { useMemo, useState } from 'react';
import Layout from '../components/Layout';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { Client, Fund, ShareRegisterEntry, getShareRegister, getClients, getFunds, updateShareRegisterEntry, deleteShareRegisterEntry } from '../lib/api';
import { useAuth } from '../lib/auth';
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

const EVENT_TYPES = ['seed', 'subscription', 'redemption', 'fee_deduction'];

export default function Page({ rows: initialRows, funds, clients, error }: Props) {
  const { t } = useI18n();
  const { hasPermission, user } = useAuth();
  const { showToast } = useToast();
  const isAdmin = user?.role === 'admin';

  const [rows, setRows] = useState(initialRows);
  const [filterFundId, setFilterFundId] = useState('');
  const [filterClientId, setFilterClientId] = useState('');
  const [editingEntry, setEditingEntry] = useState<ShareRegisterEntry | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Edit form state
  const [editEventDate, setEditEventDate] = useState('');
  const [editEventType, setEditEventType] = useState('');
  const [editSharesDelta, setEditSharesDelta] = useState('');
  const [editSharesAfter, setEditSharesAfter] = useState('');
  const [editNavPerShare, setEditNavPerShare] = useState('');
  const [editAmountUsd, setEditAmountUsd] = useState('');
  const [editNote, setEditNote] = useState('');

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

  function openEdit(entry: ShareRegisterEntry) {
    setEditEventDate(entry.event_date?.slice(0, 10) || '');
    setEditEventType(entry.event_type);
    setEditSharesDelta(String(entry.shares_delta));
    setEditSharesAfter(String(entry.shares_after));
    setEditNavPerShare(String(entry.nav_per_share));
    setEditAmountUsd(entry.amount_usd != null ? String(entry.amount_usd) : '');
    setEditNote(entry.note || '');
    setEditingEntry(entry);
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingEntry) return;
    setSubmitting(true);
    try {
      const updated = await updateShareRegisterEntry(editingEntry.id, {
        event_date: editEventDate,
        event_type: editEventType,
        shares_delta: Number(editSharesDelta),
        shares_after: Number(editSharesAfter),
        nav_per_share: Number(editNavPerShare),
        amount_usd: editAmountUsd ? Number(editAmountUsd) : null,
        note: editNote || null,
      });
      setRows(prev => prev.map(r => r.id === updated.id ? updated : r));
      setEditingEntry(null);
      showToast('Register entry updated.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to update.', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(entryId: number) {
    if (!confirm(t('confirmDeleteRegister'))) return;
    try {
      await deleteShareRegisterEntry(entryId);
      setRows(prev => prev.filter(r => r.id !== entryId));
      showToast('Register entry deleted.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to delete.', 'error');
    }
  }

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
                {[t('date'), t('fund'), t('client'), t('eventType'), t('amountUsd'), t('sharesDelta'), t('sharesAfter'), t('navPerShare'), t('note'), ...(isAdmin ? [''] : [])]
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
                    <td style={{ padding: '8px 10px' }}>{row.client_id ? (clientMap[row.client_id] ?? `#${row.client_id}`) : '—'}</td>
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
                    {isAdmin && (
                      <td style={{ padding: '8px 10px', whiteSpace: 'nowrap' }}>
                        <button
                          style={{ ...styles.buttonSecondary, padding: '3px 8px', fontSize: 12, marginRight: 4 }}
                          onClick={() => openEdit(row)}
                        >
                          {t('editEntry')}
                        </button>
                        <button
                          style={{ ...styles.buttonSecondary, padding: '3px 8px', fontSize: 12, color: colors.danger, borderColor: colors.danger }}
                          onClick={() => handleDelete(row.id)}
                        >
                          {t('deleteEntry')}
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <Modal isOpen={!!editingEntry} onClose={() => setEditingEntry(null)} title={t('editRegisterEntry')}>
        <form onSubmit={handleEditSubmit} style={{ display: 'grid', gap: 12 }}>
          <FormField label={t('date')}>
            <input type="date" style={styles.input} value={editEventDate} onChange={e => setEditEventDate(e.target.value)} disabled={submitting} required />
          </FormField>
          <FormField label={t('eventType')}>
            <select style={styles.input} value={editEventType} onChange={e => setEditEventType(e.target.value)} disabled={submitting}>
              {EVENT_TYPES.map(et => <option key={et} value={et}>{et}</option>)}
            </select>
          </FormField>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <FormField label={t('sharesDelta')}>
              <input type="number" step="any" style={styles.input} value={editSharesDelta} onChange={e => setEditSharesDelta(e.target.value)} disabled={submitting} required />
            </FormField>
            <FormField label={t('sharesAfter')}>
              <input type="number" step="any" style={styles.input} value={editSharesAfter} onChange={e => setEditSharesAfter(e.target.value)} disabled={submitting} required />
            </FormField>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <FormField label={t('navPerShare')}>
              <input type="number" step="any" style={styles.input} value={editNavPerShare} onChange={e => setEditNavPerShare(e.target.value)} disabled={submitting} required />
            </FormField>
            <FormField label={t('amountUsd')}>
              <input type="number" step="any" style={styles.input} value={editAmountUsd} onChange={e => setEditAmountUsd(e.target.value)} disabled={submitting} />
            </FormField>
          </div>
          <FormField label={t('note')}>
            <input style={styles.input} value={editNote} onChange={e => setEditNote(e.target.value)} disabled={submitting} />
          </FormField>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" style={styles.buttonSecondary} onClick={() => setEditingEntry(null)} disabled={submitting}>{t('cancel')}</button>
            <button type="submit" style={styles.buttonPrimary} disabled={submitting}>
              {submitting ? t('saving') : t('saveAndNext')}
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
