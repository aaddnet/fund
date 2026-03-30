import { useMemo, useState } from 'react';
import FormField from '../components/FormField';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { createNav, deleteNav, getFunds, getNav, Fund, NavRecord, NavRebuildResult, rebuildNavBatch } from '../lib/api';
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
  const { showToast } = useToast();
  const canWriteNav = hasPermission('nav.write');

  const defaultFundId = String(funds[0]?.id ?? 1);
  const [rows, setRows] = useState(nav);
  const [activeTab, setActiveTab] = useState<'ledger' | 'rebuild'>('ledger');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [fundId, setFundId] = useState(defaultFundId);
  const [navDate, setNavDate] = useState('2026-06-30');
  const [forceRecalc, setForceRecalc] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const fundMap = useMemo(() => Object.fromEntries(funds.map(f => [f.id, f.name])), [funds]);

  // Rebuild state
  const [rebuildFundId, setRebuildFundId] = useState(defaultFundId);
  const [rebuildStart, setRebuildStart] = useState('2018-01-01');
  const [rebuildEnd, setRebuildEnd] = useState('2025-12-31');
  const [rebuildFreq, setRebuildFreq] = useState<'quarterly' | 'yearly' | 'monthly'>('quarterly');
  const [rebuildForce, setRebuildForce] = useState(false);
  const [rebuildResults, setRebuildResults] = useState<NavRebuildResult[]>([]);
  const [rebuilding, setRebuilding] = useState(false);

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
      const created = await createNav({ fund_id: Number(fundId), nav_date: navDate, force: forceRecalc });
      setRows((current) => {
        const merged = [created, ...current.filter((item) => item.id !== created.id)];
        return merged.sort((a, b) => b.nav_date.localeCompare(a.nav_date));
      });
      showToast(t('navSuccess', { fundId: created.fund_id, date: created.nav_date }), 'success');
      setIsModalOpen(false);
    } catch (submitError) {
      showToast(submitError instanceof Error ? submitError.message : t('navFailed'), 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRebuild() {
    if (!canWriteNav) { showToast(t('permissionDenied'), 'error'); return; }
    setRebuilding(true);
    setRebuildResults([]);
    try {
      const res = await rebuildNavBatch({
        fund_id: Number(rebuildFundId),
        start_date: rebuildStart,
        end_date: rebuildEnd,
        frequency: rebuildFreq,
        force: rebuildForce,
      });
      setRebuildResults(res.results);
      const ok = res.results.filter(r => r.status === 'ok').length;
      const err = res.results.filter(r => r.status === 'error').length;
      showToast(`批量重建完成：成功 ${ok} 个，失败 ${err} 个`, ok > 0 && err === 0 ? 'success' : 'error');
      // Refresh NAV list
      const updated = await getNav(Number(rebuildFundId));
      setRows(prev => {
        const others = prev.filter(r => r.fund_id !== Number(rebuildFundId));
        return [...updated, ...others].sort((a, b) => b.nav_date.localeCompare(a.nav_date));
      });
    } catch (err) {
      showToast(err instanceof Error ? err.message : '批量重建失败', 'error');
    } finally {
      setRebuilding(false);
    }
  }

  return (
    <Layout title={t('navTitle')} subtitle={t('navSubtitle')} requiredPermission='nav.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: '#dc2626' }}>{t('backendWarning')}: {error}</div> : null}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['ledger', 'rebuild'] as const).map(tab => (
            <button
              key={tab}
              style={{ ...styles.buttonSecondary, ...(activeTab === tab ? { background: colors.primary, color: '#fff', borderColor: colors.primary } : {}) }}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'ledger' ? 'NAV 台账' : '历史重建'}
            </button>
          ))}
        </div>
        {canWriteNav && activeTab === 'ledger' && (
          <button style={styles.buttonPrimary} onClick={() => setIsModalOpen(true)}>+ Calculate NAV</button>
        )}
      </div>

      {activeTab === 'ledger' ? (
        <>
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
                { key: 'fund', title: t('fund'), render: (item) => `${fundMap[item.fund_id] ?? item.fund_name ?? 'Fund'} #${item.fund_id}` },
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
        </>
      ) : (
        // Rebuild tab
        <div style={{ ...styles.card, marginTop: 0 }}>
          <h3 style={{ marginTop: 0 }}>历史 NAV 批量重建</h3>
          <p style={{ color: colors.muted, marginTop: 0 }}>
            按指定频率批量计算历史 NAV 快照。请确保在执行前已完成 TASK-01~05 的代码修复和数据重新导入。
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <FormField label="基金">
              <select style={styles.input} value={rebuildFundId} onChange={e => setRebuildFundId(e.target.value)} disabled={rebuilding}>
                {funds.map(f => <option key={f.id} value={f.id}>#{f.id} · {f.name}</option>)}
              </select>
            </FormField>
            <FormField label="频率">
              <select style={styles.input} value={rebuildFreq} onChange={e => setRebuildFreq(e.target.value as any)} disabled={rebuilding}>
                <option value="quarterly">季度（每季末）</option>
                <option value="yearly">年度（每年末）</option>
                <option value="monthly">月度（每月末）</option>
              </select>
            </FormField>
            <FormField label="开始日期">
              <input style={styles.input} type="date" value={rebuildStart} onChange={e => setRebuildStart(e.target.value)} disabled={rebuilding} />
            </FormField>
            <FormField label="结束日期">
              <input style={styles.input} type="date" value={rebuildEnd} onChange={e => setRebuildEnd(e.target.value)} disabled={rebuilding} />
            </FormField>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer', marginBottom: 16 }}>
            <input type="checkbox" checked={rebuildForce} onChange={e => setRebuildForce(e.target.checked)} disabled={rebuilding} />
            强制覆盖已存在的 NAV 记录
          </label>
          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            <button
              style={{ ...styles.buttonPrimary, opacity: (rebuilding || !canWriteNav) ? 0.5 : 1 }}
              disabled={rebuilding || !canWriteNav}
              onClick={handleRebuild}
            >
              {rebuilding ? '重建中...' : '开始重建'}
            </button>
          </div>

          {rebuildResults.length > 0 && (
            <>
              <h4 style={{ marginBottom: 8 }}>重建结果</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f9fafb' }}>
                      {['日期', 'NAV/份额', '总资产(USD)', '状态', '备注'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rebuildResults.map((r, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '8px 12px' }}>{r.date}</td>
                        <td style={{ padding: '8px 12px' }}>{r.nav_per_share != null ? formatNumber(r.nav_per_share) : '—'}</td>
                        <td style={{ padding: '8px 12px' }}>{r.total_assets_usd != null ? formatNumber(r.total_assets_usd) : '—'}</td>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{ color: r.status === 'ok' ? colors.success : colors.danger }}>
                            {r.status === 'ok' ? '✅ 成功' : '❌ 失败'}
                          </span>
                        </td>
                        <td style={{ padding: '8px 12px', color: colors.muted }}>{r.msg || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={t('calculateNavCta')}>
        <form onSubmit={handleCreateNav} style={{ display: 'grid', gap: 14 }}>
          <FormField label={t('fund')}>
            <select style={styles.input} value={fundId} onChange={(event) => setFundId(event.target.value)} disabled={submitting}>
              {funds.map((fund) => (
                <option key={fund.id} value={fund.id}>
                  #{fund.id} · {fund.name}
                </option>
              ))}
            </select>
          </FormField>
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
    const [nav, fundData] = await Promise.all([getNav(undefined, auth.accessToken), getFunds(1, 50, auth.accessToken)]);
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, nav, funds: fundData.items ?? [] } };
  } catch (error) {
    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, nav: [], funds: [], error: error instanceof Error ? error.message : 'unknown error' } };
  }
}
