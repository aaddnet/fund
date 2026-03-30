import { useState } from 'react';
import Layout from '../components/Layout';
import FormField from '../components/FormField';
import { useToast } from '../components/Toast';
import { Client, Fund, activateFund, createFund, createSeedCapital, getFunds, getClients, updateFund } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  funds: Fund[];
  clients: Client[];
  error?: string;
};

const TOTAL_STEPS = 7;

export default function Page({ funds: initialFunds, clients, error }: Props) {
  const { t } = useI18n();
  const { showToast } = useToast();

  const [step, setStep] = useState(1);
  const [funds, setFunds] = useState<Fund[]>(initialFunds);

  // Step 1 — select / create fund
  const [selectedFundId, setSelectedFundId] = useState('');
  const [newFundName, setNewFundName] = useState('');
  const [newFundCurrency, setNewFundCurrency] = useState('USD');
  const [isCreatingFund, setIsCreatingFund] = useState(false);
  const [fundCreating, setFundCreating] = useState(false);

  // Step 2 — fund config
  const [fundCode, setFundCode] = useState('');
  const [fundType, setFundType] = useState('private_equity');
  const [hurdleRate, setHurdleRate] = useState('');
  const [perfFeeRate, setPerfFeeRate] = useState('');
  const [perfFeeFrequency, setPerfFeeFrequency] = useState('annual');
  const [subscriptionCycle, setSubscriptionCycle] = useState('quarterly');
  const [navDecimal, setNavDecimal] = useState('6');
  const [shareDecimal, setShareDecimal] = useState('6');
  const [description, setDescription] = useState('');
  const [configSaving, setConfigSaving] = useState(false);

  // Step 3 — seed capital
  const [seedClientId, setSeedClientId] = useState('');
  const [seedAmount, setSeedAmount] = useState('');
  const [seedDate, setSeedDate] = useState('');
  const [seedSaving, setSeedSaving] = useState(false);
  const [seedResult, setSeedResult] = useState<{ shares_issued: number } | null>(null);

  // Step 7 — activate
  const [activating, setActivating] = useState(false);
  const [activated, setActivated] = useState(false);

  const selectedFund = funds.find(f => String(f.id) === selectedFundId);

  async function handleCreateFund() {
    if (!newFundName.trim()) return;
    setFundCreating(true);
    try {
      const created = await createFund({ name: newFundName.trim(), base_currency: newFundCurrency });
      setFunds(prev => [...prev, created]);
      setSelectedFundId(String(created.id));
      setIsCreatingFund(false);
      setNewFundName('');
      showToast(`Fund "${created.name}" created.`, 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to create fund.', 'error');
    } finally {
      setFundCreating(false);
    }
  }

  async function handleSaveConfig() {
    if (!selectedFundId) return;
    setConfigSaving(true);
    try {
      const updated = await updateFund(Number(selectedFundId), {
        fund_code: fundCode || undefined,
        fund_type: fundType,
        hurdle_rate: hurdleRate ? Number(hurdleRate) : undefined,
        perf_fee_rate: perfFeeRate ? Number(perfFeeRate) : undefined,
        perf_fee_frequency: perfFeeFrequency || undefined,
        subscription_cycle: subscriptionCycle || undefined,
        nav_decimal: Number(navDecimal),
        share_decimal: Number(shareDecimal),
        description: description || undefined,
      });
      setFunds(prev => prev.map(f => f.id === updated.id ? updated : f));
      showToast(t('fundConfigured'), 'success');
      setStep(3);
    } catch (err: any) {
      showToast(err.message || 'Failed to save config.', 'error');
    } finally {
      setConfigSaving(false);
    }
  }

  async function handleSeedCapital() {
    if (!selectedFundId || !seedClientId || !seedAmount || !seedDate) return;
    setSeedSaving(true);
    try {
      const result = await createSeedCapital(Number(selectedFundId), {
        client_id: Number(seedClientId),
        amount_usd: Number(seedAmount),
        seed_date: seedDate,
      });
      setSeedResult(result);
      showToast(t('seedSuccess', { shares: result.shares_issued.toFixed(6) }), 'success');
      setStep(4);
    } catch (err: any) {
      showToast(err.message || 'Failed to record seed capital.', 'error');
    } finally {
      setSeedSaving(false);
    }
  }

  async function handleActivate() {
    if (!selectedFundId) return;
    setActivating(true);
    try {
      const updated = await activateFund(Number(selectedFundId));
      setFunds(prev => prev.map(f => f.id === updated.id ? updated : f));
      setActivated(true);
      showToast(t('fundActivated'), 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to activate fund.', 'error');
    } finally {
      setActivating(false);
    }
  }

  const stepLabel = t('stepOf', { step, total: TOTAL_STEPS });

  return (
    <Layout title={t('initializeTitle')} subtitle={t('initializeSubtitle')} requiredPermission="clients.write">
      {error ? <div style={{ ...styles.card, color: colors.danger, marginBottom: 16 }}>{error}</div> : null}

      {/* Step indicator */}
      <div style={{ ...styles.card, marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map(s => (
          <div
            key={s}
            onClick={() => s < step && setStep(s)}
            style={{
              width: 32, height: 32, borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700, fontSize: 13,
              background: s === step ? colors.primary : s < step ? '#d1fae5' : colors.border,
              color: s === step ? '#fff' : s < step ? '#16a34a' : colors.muted,
              cursor: s < step ? 'pointer' : 'default',
              transition: 'all 0.2s',
            }}
          >
            {s}
          </div>
        ))}
        <span style={{ marginLeft: 8, color: colors.muted, fontSize: 13 }}>{stepLabel}</span>
      </div>

      {/* Step 1: Select / Create Fund */}
      {step === 1 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Step 1 — Select or Create a Fund</h3>
          <FormField label={t('selectFund')}>
            <select style={styles.input} value={selectedFundId} onChange={e => setSelectedFundId(e.target.value)}>
              <option value="">— Select existing fund —</option>
              {funds.map(f => <option key={f.id} value={f.id}>{f.name} ({f.status || 'draft'})</option>)}
            </select>
          </FormField>
          <div style={{ margin: '12px 0', color: colors.muted, fontSize: 13 }}>— or —</div>
          {isCreatingFund ? (
            <div style={{ display: 'grid', gap: 10 }}>
              <FormField label="Fund Name">
                <input style={styles.input} value={newFundName} onChange={e => setNewFundName(e.target.value)} disabled={fundCreating} />
              </FormField>
              <FormField label="Base Currency">
                <input style={styles.input} value={newFundCurrency} onChange={e => setNewFundCurrency(e.target.value.toUpperCase())} maxLength={10} disabled={fundCreating} />
              </FormField>
              <div style={{ display: 'flex', gap: 8 }}>
                <button style={styles.buttonPrimary} onClick={handleCreateFund} disabled={fundCreating || !newFundName.trim()}>
                  {fundCreating ? 'Creating...' : 'Create Fund'}
                </button>
                <button style={styles.buttonSecondary} onClick={() => setIsCreatingFund(false)} disabled={fundCreating}>Cancel</button>
              </div>
            </div>
          ) : (
            <button style={styles.buttonSecondary} onClick={() => setIsCreatingFund(true)}>+ Create New Fund</button>
          )}
          <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
            <button style={styles.buttonPrimary} disabled={!selectedFundId} onClick={() => setStep(2)}>{t('nextStep')} →</button>
          </div>
        </div>
      )}

      {/* Step 2: Configure Fund Parameters */}
      {step === 2 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Step 2 — Configure Fund Parameters</h3>
          <p style={{ color: colors.muted, fontSize: 13 }}>Fund: <strong>{selectedFund?.name}</strong></p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <FormField label={t('fundCode')}>
              <input style={styles.input} value={fundCode} onChange={e => setFundCode(e.target.value)} disabled={configSaving} />
            </FormField>
            <FormField label={t('fundType')}>
              <select style={styles.input} value={fundType} onChange={e => setFundType(e.target.value)} disabled={configSaving}>
                <option value="private_equity">{t('privateEquity')}</option>
                <option value="hedge">{t('hedge')}</option>
              </select>
            </FormField>
            <FormField label={`${t('hurdleRate')} (%)`}>
              <input type="number" step="any" style={styles.input} value={hurdleRate} onChange={e => setHurdleRate(e.target.value)} placeholder="e.g. 8" disabled={configSaving} />
            </FormField>
            <FormField label={`${t('perfFeeRate')} (%)`}>
              <input type="number" step="any" style={styles.input} value={perfFeeRate} onChange={e => setPerfFeeRate(e.target.value)} placeholder="e.g. 20" disabled={configSaving} />
            </FormField>
            <FormField label={t('perfFeeFrequency')}>
              <select style={styles.input} value={perfFeeFrequency} onChange={e => setPerfFeeFrequency(e.target.value)} disabled={configSaving}>
                <option value="annual">Annual</option>
                <option value="quarterly">Quarterly</option>
              </select>
            </FormField>
            <FormField label={t('subscriptionCycle')}>
              <select style={styles.input} value={subscriptionCycle} onChange={e => setSubscriptionCycle(e.target.value)} disabled={configSaving}>
                <option value="quarterly">Quarterly</option>
                <option value="monthly">Monthly</option>
                <option value="annual">Annual</option>
              </select>
            </FormField>
            <FormField label={t('navDecimal')}>
              <input type="number" style={styles.input} value={navDecimal} onChange={e => setNavDecimal(e.target.value)} min="2" max="8" disabled={configSaving} />
            </FormField>
            <FormField label={t('shareDecimal')}>
              <input type="number" style={styles.input} value={shareDecimal} onChange={e => setShareDecimal(e.target.value)} min="2" max="8" disabled={configSaving} />
            </FormField>
          </div>
          <FormField label={t('description')}>
            <textarea style={{ ...styles.input, height: 72 }} value={description} onChange={e => setDescription(e.target.value)} disabled={configSaving} />
          </FormField>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
            <button style={styles.buttonSecondary} onClick={() => setStep(1)} disabled={configSaving}>{t('prevStep')}</button>
            <button style={styles.buttonPrimary} onClick={handleSaveConfig} disabled={configSaving}>
              {configSaving ? 'Saving...' : `Save & ${t('nextStep')}`}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Seed Capital */}
      {step === 3 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Step 3 — Record Seed Capital</h3>
          <p style={{ color: colors.muted, fontSize: 13 }}>Fund: <strong>{selectedFund?.name}</strong> · Initial NAV = 1.000000</p>
          {seedResult && (
            <div style={{ background: '#d1fae5', borderRadius: 8, padding: '10px 14px', marginBottom: 12, fontSize: 13 }}>
              ✓ {seedResult.shares_issued.toFixed(6)} shares issued at NAV 1.000000
            </div>
          )}
          <div style={{ display: 'grid', gap: 12 }}>
            <FormField label={t('client')}>
              <select style={styles.input} value={seedClientId} onChange={e => setSeedClientId(e.target.value)} disabled={seedSaving}>
                <option value="">Select Client</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </FormField>
            <FormField label={`${t('amountUsd')} (USD)`}>
              <input type="number" step="any" style={styles.input} value={seedAmount} onChange={e => setSeedAmount(e.target.value)} placeholder="e.g. 1000000" disabled={seedSaving} />
            </FormField>
            <FormField label="Seed Date">
              <input type="date" style={styles.input} value={seedDate} onChange={e => setSeedDate(e.target.value)} disabled={seedSaving} />
            </FormField>
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
            <button style={styles.buttonSecondary} onClick={() => setStep(2)} disabled={seedSaving}>{t('prevStep')}</button>
            <button style={styles.buttonSecondary} onClick={() => setStep(4)} disabled={seedSaving}>Skip</button>
            <button style={styles.buttonPrimary} onClick={handleSeedCapital} disabled={seedSaving || !seedClientId || !seedAmount || !seedDate}>
              {seedSaving ? 'Recording...' : `Record ${t('seedCapital')}`}
            </button>
          </div>
        </div>
      )}

      {/* Steps 4-6: Guidance */}
      {step === 4 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Step 4 — Account Setup</h3>
          <p>Ensure all brokerage accounts are created and linked to this fund:</p>
          <ol style={{ color: colors.muted, fontSize: 14, lineHeight: 1.8 }}>
            <li>Go to <strong>Accounts</strong> → Create Account → select this fund, choose broker, enter account number.</li>
            <li>Link each account to the appropriate client.</li>
            <li>Accounts are used to scope positions and transactions for NAV calculation.</li>
          </ol>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
            <button style={styles.buttonSecondary} onClick={() => setStep(3)}>{t('prevStep')}</button>
            <button style={styles.buttonPrimary} onClick={() => setStep(5)}>{t('nextStep')} →</button>
          </div>
        </div>
      )}

      {step === 5 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Step 5 — Cash Positions</h3>
          <p>Record cash balances held in each account on the NAV date:</p>
          <ol style={{ color: colors.muted, fontSize: 14, lineHeight: 1.8 }}>
            <li>Go to <strong>Cash</strong> page → Add Cash Position.</li>
            <li>Select the account, currency, amount, and snapshot date (must match the NAV date you intend to calculate).</li>
            <li>Cash balances are automatically included when calculating NAV for that date.</li>
          </ol>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
            <button style={styles.buttonSecondary} onClick={() => setStep(4)}>{t('prevStep')}</button>
            <button style={styles.buttonPrimary} onClick={() => setStep(6)}>{t('nextStep')} →</button>
          </div>
        </div>
      )}

      {step === 6 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Step 6 — NAV Calculation</h3>
          <p>Calculate the first official NAV for this fund:</p>
          <ol style={{ color: colors.muted, fontSize: 14, lineHeight: 1.8 }}>
            <li>Import position snapshots via <strong>Import</strong> → select account + date → upload CSV.</li>
            <li>Ensure asset prices and FX rates exist for the target date (use Scheduler or manual entry).</li>
            <li>Go to <strong>NAV</strong> → Calculate NAV → select this fund and the NAV date.</li>
            <li>Review the calculated total assets and NAV per share.</li>
          </ol>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
            <button style={styles.buttonSecondary} onClick={() => setStep(5)}>{t('prevStep')}</button>
            <button style={styles.buttonPrimary} onClick={() => setStep(7)}>{t('nextStep')} →</button>
          </div>
        </div>
      )}

      {/* Step 7: Activate Fund */}
      {step === 7 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>Step 7 — Activate Fund</h3>
          <p style={{ color: colors.muted, fontSize: 13 }}>Fund: <strong>{selectedFund?.name}</strong> · Current status: <strong>{selectedFund?.status || 'draft'}</strong></p>
          {activated || selectedFund?.status === 'active' ? (
            <div style={{ background: '#d1fae5', borderRadius: 8, padding: '12px 16px', fontSize: 14 }}>
              ✓ Fund is <strong>active</strong>. Initialization complete!
            </div>
          ) : (
            <>
              <p>Once all setup steps are complete, activate the fund to mark it as operational.</p>
              <ul style={{ color: colors.muted, fontSize: 14, lineHeight: 1.8 }}>
                <li>Status changes from <em>draft</em> → <em>active</em></li>
                <li>Inception date will be set to today if not already configured</li>
                <li>Fund will appear in operational dashboards</li>
              </ul>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
                <button style={styles.buttonSecondary} onClick={() => setStep(6)} disabled={activating}>{t('prevStep')}</button>
                <button style={styles.buttonPrimary} onClick={handleActivate} disabled={activating}>
                  {activating ? 'Activating...' : t('activateFund')}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  try {
    const [fundData, clientData] = await Promise.all([
      getFunds(1, 100, auth.accessToken),
      getClients({ accessToken: auth.accessToken, size: 200 }),
    ]);

    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        funds: fundData.items ?? [],
        clients: clientData.items ?? [],
      },
    };
  } catch (error: any) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        funds: [],
        clients: [],
        error: error?.message || 'Failed to load data.',
      },
    };
  }
}
