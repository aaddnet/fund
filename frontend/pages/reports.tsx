import Link from 'next/link';
import { useState } from 'react';
import Layout from '../components/Layout';
import ProductTable from '../components/ProductTable';
import StatCard from '../components/StatCard';
import {
  Client,
  Fund,
  ReportBreakdownRow,
  ReportOverview,
  ReportShareFlowSeriesRow,
  getClients,
  getFunds,
  getReportOverview,
} from '../lib/api';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, formatNumber, styles } from '../lib/ui';

type Props = {
  report: ReportOverview | null;
  funds: Fund[];
  clients: Client[];
  filters: {
    periodType: string;
    periodValue: string;
    fundId: string;
    clientId: string;
    txType: string;
  };
  error?: string;
};

function MiniBarChart({ data }: { data: ReportShareFlowSeriesRow[] }) {
  if (!data.length) {
    return <p style={{ color: colors.muted, marginBottom: 0 }}>No trend data.</p>;
  }

  const maxAbs = Math.max(...data.map((item) => Math.abs(item.net_share_flow_usd)), 1);

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {data.map((item) => {
        const width = `${Math.max((Math.abs(item.net_share_flow_usd) / maxAbs) * 100, 6)}%`;
        const positive = item.net_share_flow_usd >= 0;
        return (
          <div key={item.date}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
              <span>{item.date}</span>
              <strong>{formatNumber(item.net_share_flow_usd)}</strong>
            </div>
            <div style={{ background: '#e5e7eb', borderRadius: 999, overflow: 'hidden', height: 10 }}>
              <div
                style={{
                  width,
                  height: '100%',
                  borderRadius: 999,
                  background: positive ? colors.success : colors.danger,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BreakdownTable({ title, rows, emptyText }: { title: string; rows: ReportBreakdownRow[]; emptyText: string }) {
  return (
    <div style={styles.card}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <ProductTable
        emptyText={emptyText}
        rows={rows}
        columns={[
          { key: 'key', title: 'Key', render: (item) => item.key },
          { key: 'count', title: 'Tx', render: (item) => item.share_tx_count },
          { key: 'sub', title: 'Subscribe USD', render: (item) => formatNumber(item.subscription_amount_usd) },
          { key: 'red', title: 'Redeem USD', render: (item) => formatNumber(item.redemption_amount_usd) },
          { key: 'net', title: 'Net USD', render: (item) => formatNumber(item.net_share_flow_usd) },
          { key: 'shares', title: 'Shares Δ', render: (item) => formatNumber(item.shares_delta, 8) },
        ]}
      />
    </div>
  );
}

function downloadReport(report: ReportOverview, type: 'json' | 'csv') {
  const dateTag = `${report.filters.period_value}-${report.filters.tx_type || 'all'}`;
  const filename = `report-${dateTag}.${type}`;
  const blob = type === 'json'
    ? new Blob([JSON.stringify(report, null, 2)], { type: 'application/json;charset=utf-8' })
    : new Blob([
      [
        ['date', 'fund_id', 'client_id', 'tx_type', 'amount_usd', 'shares'].join(','),
        ...report.share_history.map((item) => [item.tx_date, item.fund_id, item.client_id, item.tx_type, item.amount_usd, item.shares].join(',')),
      ].join('\n'),
    ], { type: 'text/csv;charset=utf-8' });

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

// Generate year options: current year ± 3
function yearOptions() {
  const now = new Date().getFullYear();
  return Array.from({ length: 7 }, (_, i) => now - 3 + i);
}

// Derive default period value parts from a period value string
function parsePeriodValue(type: string, value: string) {
  if (type === 'quarter') {
    const m = value.match(/^(\d{4})-(Q[1-4])$/i);
    return { year: m ? m[1] : String(new Date().getFullYear()), quarter: m ? m[2].toUpperCase() : 'Q1' };
  }
  if (type === 'year') return { year: value || String(new Date().getFullYear()), quarter: 'Q1' };
  // month: YYYY-MM
  return { year: value ? value.slice(0, 4) : String(new Date().getFullYear()), quarter: 'Q1' };
}

export default function Page({ report, funds, clients, filters, error }: Props) {
  const { t } = useI18n();

  const [periodType, setPeriodType] = useState(filters.periodType);
  const parts = parsePeriodValue(filters.periodType, filters.periodValue);
  const [qYear, setQYear] = useState(parts.year);
  const [qQuarter, setQQuarter] = useState(parts.quarter);

  // For form submission: assemble quarter value before submit
  function handleFormSubmit(e: React.FormEvent<HTMLFormElement>) {
    if (periodType === 'quarter') {
      // Inject hidden periodValue before native form submit
      const form = e.currentTarget;
      let hidden = form.querySelector<HTMLInputElement>('input[name="periodValue"][type="hidden"]');
      if (!hidden) {
        hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = 'periodValue';
        form.appendChild(hidden);
      }
      hidden.value = `${qYear}-${qQuarter}`;
    }
  }

  return (
    <Layout title={t('reportsTitle')} subtitle={t('reportsSubtitle')} requiredPermission='reports.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={styles.grid2}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('reportFilters')}</h3>
          <form method='get' style={{ display: 'grid', gap: 12 }} onSubmit={handleFormSubmit}>
            <div>
              <label style={styles.label}>{t('periodType')}</label>
              <select name='periodType' value={periodType} onChange={e => setPeriodType(e.target.value)} style={styles.input}>
                <option value='month'>{t('month')}</option>
                <option value='quarter'>{t('quarter')}</option>
                <option value='year'>{t('year')}</option>
              </select>
            </div>
            <div>
              <label style={styles.label}>{t('periodValue')}</label>
              {periodType === 'month' && (
                <input
                  type='month'
                  name='periodValue'
                  defaultValue={filters.periodType === 'month' ? filters.periodValue : `${new Date().getFullYear()}-01`}
                  style={styles.input}
                  placeholder='YYYY-MM'
                />
              )}
              {periodType === 'quarter' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <select value={qYear} onChange={e => setQYear(e.target.value)} style={{ ...styles.input, flex: 1 }}>
                    {yearOptions().map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <select value={qQuarter} onChange={e => setQQuarter(e.target.value)} style={{ ...styles.input, flex: 1 }}>
                    <option value='Q1'>Q1 (Jan–Mar)</option>
                    <option value='Q2'>Q2 (Apr–Jun)</option>
                    <option value='Q3'>Q3 (Jul–Sep)</option>
                    <option value='Q4'>Q4 (Oct–Dec)</option>
                  </select>
                </div>
              )}
              {periodType === 'year' && (
                <select
                  name='periodValue'
                  defaultValue={filters.periodType === 'year' ? filters.periodValue : String(new Date().getFullYear())}
                  style={styles.input}
                >
                  {yearOptions().map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              )}
            </div>
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
              <label style={styles.label}>{t('client')}</label>
              <select name='clientId' defaultValue={filters.clientId} style={styles.input}>
                <option value=''>{t('allClients')}</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{`#${client.id} · ${client.name}`}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={styles.label}>Share Tx Type</label>
              <select name='txType' defaultValue={filters.txType} style={styles.input}>
                <option value=''>All</option>
                <option value='subscribe'>Subscribe</option>
                <option value='redeem'>Redeem</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
              <button type='submit' style={styles.buttonPrimary}>{t('runReport')}</button>
              <a href='/reports' style={{ ...styles.buttonSecondary, textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>{t('reset')}</a>
            </div>
          </form>
        </div>

        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('reportScope')}</h3>
          {!report ? (
            <p style={{ color: colors.muted, marginBottom: 0 }}>{t('noReportData')}</p>
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              <div><strong>{t('dateRange')}:</strong> {report.filters.date_from} → {report.filters.date_to}</div>
              <div><strong>{t('fundFilter')}:</strong> {report.filters.fund_id ?? t('allFunds')}</div>
              <div><strong>{t('clientFilter')}:</strong> {report.filters.client_id ?? t('allClients')}</div>
              <div><strong>Tx type:</strong> {report.filters.tx_type || 'all'}</div>
              <div><strong>{t('shareFlow')}:</strong> {formatNumber(report.summary.net_share_flow_usd)} USD net</div>
              <div><strong>Funds touched:</strong> {report.summary.fund_count}</div>
              <div><strong>Clients touched:</strong> {report.summary.client_count}</div>
              <div><strong>Avg NAV/share:</strong> {formatNumber(report.summary.avg_nav_per_share, 6)}</div>
            </div>
          )}
        </div>
      </div>

      <div style={{ ...styles.grid3, marginTop: 16 }}>
        <StatCard label='Share Tx' value={String(report?.summary.share_tx_count ?? 0)} />
        <StatCard label={t('subscriptionsUsd')} value={formatNumber(report?.summary.subscription_amount_usd ?? 0)} tone='success' />
        <StatCard label={t('redemptionsUsd')} value={formatNumber(report?.summary.redemption_amount_usd ?? 0)} tone='warning' />
      </div>
      <div style={{ ...styles.grid3, marginTop: 16 }}>
        <StatCard label={t('netShareFlowUsd')} value={formatNumber(report?.summary.net_share_flow_usd ?? 0)} />
        <StatCard label={t('navRecords')} value={String(report?.summary.nav_record_count ?? 0)} />
        <StatCard label={t('transactions')} value={String(report?.summary.transaction_count ?? 0)} />
      </div>

      {/* RPT-01: Fund Overview Summary */}
      {report && report.breakdowns.nav_by_fund.length > 0 && (
        <div style={{ ...styles.card, marginTop: 16 }}>
          <h3 style={{ marginTop: 0, marginBottom: 12 }}>基金总览 (Fund Overview)</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
            {report.breakdowns.nav_by_fund.map(f => {
              const fundName = funds.find(fn => fn.id === f.fund_id)?.name ?? `Fund #${f.fund_id}`;
              return (
                <div key={f.fund_id} style={{ flex: '1 1 200px', border: `1px solid ${colors.border}`, borderRadius: 10, padding: '14px 18px', background: '#fff' }}>
                  <div style={{ fontSize: 11, color: colors.muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>{fundName}</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: colors.primary, marginBottom: 2 }}>
                    {formatNumber(f.latest_total_assets_usd)}
                  </div>
                  <div style={{ fontSize: 12, color: colors.muted }}>AUM (USD)</div>
                  <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 11, color: colors.muted }}>NAV / 份</div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{formatNumber(f.latest_nav_per_share, 6)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: colors.muted }}>最新日期</div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{f.latest_nav_date ?? '—'}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 12, color: colors.muted }}>
            合计 AUM: <strong>{formatNumber(report.breakdowns.nav_by_fund.reduce((s, f) => s + (f.latest_total_assets_usd ?? 0), 0))}</strong> USD
            &nbsp;·&nbsp; {report.breakdowns.nav_by_fund.length} 个基金
            &nbsp;·&nbsp; 期间: {report.filters.date_from} → {report.filters.date_to}
          </div>
        </div>
      )}

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Share Flow Trend</h3>
          <MiniBarChart data={report?.series.share_flow_by_date ?? []} />
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Latest NAV by Fund</h3>
          <ProductTable
            emptyText={t('noNavForQuery')}
            rows={report?.breakdowns.nav_by_fund ?? []}
            columns={[
              { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
              { key: 'date', title: t('date'), render: (item) => item.latest_nav_date },
              { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.latest_nav_per_share, 6) },
              { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.latest_total_assets_usd) },
              { key: 'count', title: 'Records', render: (item) => item.record_count },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <BreakdownTable title='Share Flow by Fund' rows={report?.breakdowns.by_fund ?? []} emptyText={t('noShareFlowRecords')} />
        <BreakdownTable title='Share Flow by Client' rows={report?.breakdowns.by_client ?? []} emptyText={t('noShareFlowRecords')} />
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <BreakdownTable title='Share Flow by Tx Type' rows={report?.breakdowns.by_tx_type ?? []} emptyText={t('noShareFlowRecords')} />
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Transactions by Asset</h3>
          <ProductTable
            emptyText='No transactions for this query.'
            rows={report?.breakdowns.transactions_by_asset ?? []}
            columns={[
              { key: 'asset', title: 'Asset', render: (item) => item.asset_code },
              { key: 'count', title: 'Tx', render: (item) => item.transaction_count },
              { key: 'notional', title: 'Gross Notional', render: (item) => formatNumber(item.gross_notional_estimate) },
              { key: 'latest', title: 'Latest Trade', render: (item) => item.latest_trade_date },
            ]}
          />
        </div>
      </div>

      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('shareFlowDetail')}</h3>
        <ProductTable
          emptyText={t('noShareFlowRecords')}
          rows={report?.share_history ?? []}
          columns={[
            { key: 'date', title: t('date'), render: (item) => item.tx_date },
            { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
            { key: 'client', title: t('client'), render: (item) => item.client_id },
            { key: 'type', title: t('type'), render: (item) => item.tx_type },
            { key: 'amount', title: t('amountUsd'), render: (item) => formatNumber(item.amount_usd) },
            { key: 'shares', title: t('sharesLabel'), render: (item) => formatNumber(item.shares, 8) },
          ]}
        />
      </div>

      <div style={{ ...styles.grid2, marginTop: 16 }}>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('navRecords')}</h3>
          <ProductTable
            emptyText={t('noNavForQuery')}
            rows={report?.nav_records ?? []}
            columns={[
              { key: 'date', title: t('date'), render: (item) => item.nav_date },
              { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
              { key: 'nav', title: 'NAV / Share', render: (item) => formatNumber(item.nav_per_share, 6) },
              { key: 'assets', title: 'Assets USD', render: (item) => formatNumber(item.total_assets_usd) },
            ]}
          />
        </div>
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>{t('feeRecords')}</h3>
          <ProductTable
            emptyText={t('noFeeForQuery')}
            rows={report?.fee_records ?? []}
            columns={[
              { key: 'date', title: t('date'), render: (item) => item.fee_date },
              { key: 'fund', title: t('fund'), render: (item) => item.fund_id },
              { key: 'rate', title: 'Fee Rate', render: (item) => formatNumber(item.fee_rate, 4) },
              { key: 'amount', title: t('amountUsd'), render: (item) => formatNumber(item.fee_amount_usd) },
            ]}
          />
        </div>
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const periodType = typeof context.query.periodType === 'string' ? context.query.periodType : 'quarter';
  const periodValue = typeof context.query.periodValue === 'string' ? context.query.periodValue : '2026-Q1';
  const fundId = typeof context.query.fundId === 'string' ? context.query.fundId : '';
  const clientId = typeof context.query.clientId === 'string' ? context.query.clientId : '';
  const txType = typeof context.query.txType === 'string' ? context.query.txType : '';

  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  try {
    const [report, fundData, clientData] = await Promise.all([
      getReportOverview({
        accessToken: auth.accessToken,
        periodType,
        periodValue,
        fundId: fundId ? Number(fundId) : undefined,
        clientId: clientId ? Number(clientId) : undefined,
        txType: txType || undefined,
      }),
      getFunds(1, 50, auth.accessToken),
      getClients({ accessToken: auth.accessToken }),
    ]);

    return { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale, report, funds: fundData.items ?? [], clients: clientData.items ?? [], filters: { periodType, periodValue, fundId, clientId, txType } } };
  } catch (error) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        report: null,
        funds: [],
        clients: [],
        filters: { periodType, periodValue, fundId, clientId, txType },
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
