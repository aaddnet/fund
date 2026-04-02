import { useRouter } from 'next/router';
import { useState } from 'react';
import Layout from '../../components/Layout';
import {
  Account,
  TransactionCreateRequest,
  createTransaction,
  getAccounts,
} from '../../lib/api';
import { requirePageAuth } from '../../lib/pageAuth';
import { colors, styles } from '../../lib/ui';

type FormType = 'trade' | 'cash' | 'interest' | 'dividend' | 'fx' | 'option' | 'lending' | 'accrual' | 'corporate';

type Props = {
  accounts: Account[];
  accessToken: string;
};

const TYPE_CONFIG: { key: FormType; label: string; emoji: string; desc: string }[] = [
  { key: 'trade',    label: '股票买卖',   emoji: '📈', desc: 'stock_buy / stock_sell' },
  { key: 'option',   label: '期权交易',   emoji: '🔧', desc: 'option_buy / sell / expire / exercise' },
  { key: 'cash',     label: '资金往来',   emoji: '💵', desc: '入金 / 出金' },
  { key: 'interest', label: '利息费用',   emoji: '💸', desc: '利息 / 各类费用' },
  { key: 'dividend', label: '股息收入',   emoji: '🏦', desc: 'dividend / PIL' },
  { key: 'fx',       label: '换汇交易',   emoji: '💱', desc: 'fx_trade' },
  { key: 'lending',  label: '证券出借',   emoji: '🔄', desc: 'lending_out / return / income' },
  { key: 'accrual',  label: '应计项目',   emoji: '📋', desc: 'interest / dividend accrual' },
  { key: 'corporate',label: '企业行动',   emoji: '🏢', desc: '拆股 / 配股 / 分拆 / 合并' },
];

const CURRENCIES = ['USD', 'HKD', 'CNY', 'EUR', 'SGD', 'AUD'];
const EXCHANGES = ['US', 'HK', 'CN', 'SG', 'EU'];
const ASSET_TYPES = ['stock', 'etf', 'adr', 'crypto', 'option', 'fund', 'warrant'];

export default function NewTransactionPage({ accounts, accessToken }: Props) {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [formType, setFormType] = useState<FormType>('trade');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const today = new Date().toISOString().slice(0, 10);

  // Common fields
  const [accountId, setAccountId] = useState(accounts[0]?.id ? String(accounts[0].id) : '');
  const [tradeDate, setTradeDate] = useState(today);
  const [settleDate, setSettleDate] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [description, setDescription] = useState('');

  // Trade fields
  const [direction, setDirection] = useState<'buy' | 'sell'>('buy');
  const [assetCode, setAssetCode] = useState('');
  const [assetName, setAssetName] = useState('');
  const [assetType, setAssetType] = useState('stock');
  const [exchange, setExchange] = useState('US');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [commission, setCommission] = useState('');
  const [txFee, setTxFee] = useState('');
  const [otherFee, setOtherFee] = useState('');
  const [realizedPnl, setRealizedPnl] = useState('');
  const [costBasis, setCostBasis] = useState('');

  // Cash fields
  const [cashSubtype, setCashSubtype] = useState('deposit_eft');
  const [cashAmount, setCashAmount] = useState('');
  const [counterpartyAccount, setCounterpartyAccount] = useState('');

  // Interest/fee fields
  const [interestSubtype, setInterestSubtype] = useState('interest_debit');
  const [interestAmount, setInterestAmount] = useState('');
  const [accrualStart, setAccrualStart] = useState('');
  const [accrualEnd, setAccrualEnd] = useState('');
  const [relatedAsset, setRelatedAsset] = useState('');

  // Dividend fields
  const [divSubtype, setDivSubtype] = useState('dividend');
  const [divAmount, setDivAmount] = useState('');
  const [divFee, setDivFee] = useState('');

  // FX fields
  const [fxFromCurrency, setFxFromCurrency] = useState('USD');
  const [fxFromAmount, setFxFromAmount] = useState('');
  const [fxToCurrency, setFxToCurrency] = useState('HKD');
  const [fxToAmount, setFxToAmount] = useState('');

  // Option fields
  const [optionSubtype, setOptionSubtype] = useState('option_buy');
  const [optionCode, setOptionCode] = useState('');
  const [optionUnderlying, setOptionUnderlying] = useState('');
  const [optionType, setOptionType] = useState<'call' | 'put'>('call');
  const [optionExpiry, setOptionExpiry] = useState('');
  const [optionStrike, setOptionStrike] = useState('');
  const [optionMultiplier, setOptionMultiplier] = useState('100');
  const [optionQty, setOptionQty] = useState('');
  const [optionPremium, setOptionPremium] = useState('');

  // Lending fields
  const [lendingSubtype, setLendingSubtype] = useState('lending_out');
  const [lendingAsset, setLendingAsset] = useState('');
  const [lendingQty, setLendingQty] = useState('');
  const [collateralAmount, setCollateralAmount] = useState('');
  const [lendingRate, setLendingRate] = useState('');

  // Accrual fields
  const [accrualSubtype, setAccrualSubtype] = useState('interest_accrual');
  const [accrualAmount, setAccrualAmount] = useState('');
  const [isReversal, setIsReversal] = useState(false);

  // Corporate fields
  const [corpSubtype, setCorpSubtype] = useState('stock_split');
  const [corpAsset, setCorpAsset] = useState('');
  const [corpRatio, setCorpRatio] = useState('');
  const [corpNewCode, setCorpNewCode] = useState('');
  const [corpAmount, setCorpAmount] = useState('');

  const num = (v: string) => v ? Number(v) : undefined;
  const neg = (v: string) => v ? -Math.abs(Number(v)) : undefined;  // fees always negative

  const grossAmount = () => {
    if (!quantity || !price) return undefined;
    const q = Math.abs(Number(quantity));
    const p = Number(price);
    return direction === 'buy' ? -(q * p) : q * p;
  };

  const netCash = () => {
    const g = grossAmount() || 0;
    const c = Number(commission || 0);
    const t = Number(txFee || 0);
    const o = Number(otherFee || 0);
    return g + c + t + o;
  };

  const fxRate = () => {
    const from = Math.abs(Number(fxFromAmount || 0));
    const to = Math.abs(Number(fxToAmount || 0));
    if (!from) return null;
    return (to / from).toFixed(6);
  };

  const buildPayload = (): TransactionCreateRequest => {
    const base = {
      account_id: Number(accountId),
      trade_date: tradeDate,
      settle_date: settleDate || undefined,
      currency,
      description: description || undefined,
      source: 'manual',
    };

    switch (formType) {
      case 'trade':
        return {
          ...base,
          tx_category: 'TRADE',
          tx_type: direction === 'buy' ? 'stock_buy' : 'stock_sell',
          asset_code: assetCode.toUpperCase(),
          asset_name: assetName || undefined,
          asset_type: assetType,
          exchange,
          quantity: direction === 'buy' ? Math.abs(Number(quantity)) : -Math.abs(Number(quantity)),
          price: num(price),
          gross_amount: grossAmount(),
          commission: commission ? -Math.abs(Number(commission)) : undefined,
          transaction_fee: txFee ? -Math.abs(Number(txFee)) : undefined,
          other_fee: otherFee ? -Math.abs(Number(otherFee)) : undefined,
          realized_pnl: realizedPnl ? num(realizedPnl) : undefined,
          cost_basis: costBasis ? num(costBasis) : undefined,
        };

      case 'option':
        return {
          ...base,
          tx_category: 'TRADE',
          tx_type: optionSubtype,
          asset_code: optionCode.toUpperCase() || undefined,
          option_underlying: optionUnderlying.toUpperCase() || undefined,
          option_type: optionType,
          option_expiry: optionExpiry || undefined,
          option_strike: num(optionStrike),
          option_multiplier: Number(optionMultiplier || 100),
          quantity: optionSubtype.includes('buy') ? Math.abs(Number(optionQty)) : -Math.abs(Number(optionQty)),
          price: num(optionPremium),
          gross_amount: optionSubtype.includes('buy')
            ? -(Math.abs(Number(optionQty)) * Number(optionPremium || 0) * Number(optionMultiplier || 100))
            : Math.abs(Number(optionQty)) * Number(optionPremium || 0) * Number(optionMultiplier || 100),
          commission: commission ? -Math.abs(Number(commission)) : undefined,
          transaction_fee: txFee ? -Math.abs(Number(txFee)) : undefined,
        };

      case 'cash':
        return {
          ...base,
          tx_category: 'CASH',
          tx_type: cashSubtype,
          gross_amount: cashSubtype === 'withdrawal' ? -Math.abs(Number(cashAmount)) : Math.abs(Number(cashAmount)),
          counterparty_account: counterpartyAccount || undefined,
        };

      case 'interest':
        return {
          ...base,
          tx_category: 'CASH',
          tx_type: interestSubtype,
          gross_amount: -Math.abs(Number(interestAmount)),
          accrual_period_start: accrualStart || undefined,
          accrual_period_end: accrualEnd || undefined,
          asset_code: relatedAsset ? relatedAsset.toUpperCase() : undefined,
        };

      case 'dividend':
        return {
          ...base,
          tx_category: 'CASH',
          tx_type: divSubtype,
          gross_amount: Math.abs(Number(divAmount)),
          other_fee: divFee ? -Math.abs(Number(divFee)) : undefined,
          asset_code: relatedAsset ? relatedAsset.toUpperCase() : undefined,
        };

      case 'fx':
        return {
          ...base,
          tx_category: 'FX',
          tx_type: 'fx_trade',
          currency: fxFromCurrency,
          fx_from_currency: fxFromCurrency,
          fx_from_amount: -Math.abs(Number(fxFromAmount)),
          fx_to_currency: fxToCurrency,
          fx_to_amount: Math.abs(Number(fxToAmount)),
          fx_rate: num(fxRate() || ''),
          commission: commission ? -Math.abs(Number(commission)) : undefined,
        };

      case 'lending':
        return {
          ...base,
          tx_category: 'LENDING',
          tx_type: lendingSubtype,
          lending_asset_code: lendingAsset.toUpperCase() || undefined,
          lending_quantity: lendingSubtype === 'lending_out' ? -Math.abs(Number(lendingQty)) : Math.abs(Number(lendingQty)),
          collateral_amount: collateralAmount ? Math.abs(Number(collateralAmount)) : undefined,
          lending_rate_pct: lendingRate ? num(lendingRate) : undefined,
          ...(lendingSubtype === 'lending_income' ? { gross_amount: Math.abs(Number(cashAmount)) } : {}),
        };

      case 'accrual':
        return {
          ...base,
          tx_category: 'ACCRUAL',
          tx_type: accrualSubtype,
          gross_amount: isReversal ? Math.abs(Number(accrualAmount)) : -Math.abs(Number(accrualAmount)),
          is_accrual_reversal: isReversal,
          accrual_type: accrualSubtype,
          accrual_period_start: accrualStart || undefined,
          accrual_period_end: accrualEnd || undefined,
          asset_code: relatedAsset ? relatedAsset.toUpperCase() : undefined,
        };

      case 'corporate':
        return {
          ...base,
          tx_category: 'CORPORATE',
          tx_type: corpSubtype,
          asset_code: corpAsset.toUpperCase(),
          corporate_ratio: corpRatio ? num(corpRatio) : undefined,
          corporate_new_code: corpNewCode || undefined,
          gross_amount: corpAmount ? -Math.abs(Number(corpAmount)) : undefined,
        };

      default:
        return { ...base, tx_category: 'CASH', tx_type: 'adjustment' };
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await createTransaction(buildPayload(), accessToken);
      router.push('/transactions');
    } catch (err: any) {
      setError(err?.message || '提交失败，请检查填写内容');
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle = {
    padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`,
    fontSize: 13, width: '100%', boxSizing: 'border-box' as const,
  };
  const labelStyle = { fontSize: 12, color: colors.muted, display: 'block', marginBottom: 4 };
  const fieldWrap = { marginBottom: 14 };

  return (
    <Layout title="新增交易" subtitle="手动录入交易记录" requiredPermission="accounts.write">
      {/* Step 1: choose form type */}
      {step === 1 && (
        <div style={styles.card}>
          <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>选择交易类型</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
            {TYPE_CONFIG.map(({ key, label, emoji, desc }) => (
              <button
                key={key}
                onClick={() => { setFormType(key); setStep(2); }}
                style={{
                  padding: '16px 12px', borderRadius: 8, textAlign: 'left',
                  border: `2px solid ${colors.border}`, background: '#fafafa',
                  cursor: 'pointer',
                  transition: 'border-color 0.15s',
                }}
              >
                <div style={{ fontSize: 24, marginBottom: 6 }}>{emoji}</div>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 11, color: colors.muted }}>{desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 2: form */}
      {step === 2 && (
        <div>
          {/* Breadcrumb */}
          <div style={{ marginBottom: 12 }}>
            <button onClick={() => setStep(1)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: colors.primary, fontSize: 13 }}>
              ← 返回选择类型
            </button>
            <span style={{ fontSize: 13, color: colors.muted, marginLeft: 8 }}>
              当前: {TYPE_CONFIG.find(t => t.key === formType)?.emoji} {TYPE_CONFIG.find(t => t.key === formType)?.label}
            </span>
          </div>

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>

              {/* Common fields card */}
              <div style={styles.card}>
                <h4 style={{ margin: '0 0 12px', fontSize: 14, color: colors.muted }}>基本信息</h4>

                <div style={fieldWrap}>
                  <label style={labelStyle}>账户 *</label>
                  <select value={accountId} onChange={e => setAccountId(e.target.value)} required style={inputStyle}>
                    {accounts.map(a => <option key={a.id} value={String(a.id)}>{a.broker} · {a.account_no}</option>)}
                  </select>
                </div>

                <div style={fieldWrap}>
                  <label style={labelStyle}>交易日期 *</label>
                  <input type="date" value={tradeDate} onChange={e => setTradeDate(e.target.value)} required style={inputStyle} />
                </div>

                <div style={fieldWrap}>
                  <label style={labelStyle}>结算日期（可空）</label>
                  <input type="date" value={settleDate} onChange={e => setSettleDate(e.target.value)} style={inputStyle} />
                </div>

                {formType !== 'fx' && (
                  <div style={fieldWrap}>
                    <label style={labelStyle}>货币 *</label>
                    <select value={currency} onChange={e => setCurrency(e.target.value)} style={inputStyle}>
                      {CURRENCIES.map(c => <option key={c}>{c}</option>)}
                    </select>
                  </div>
                )}

                <div style={fieldWrap}>
                  <label style={labelStyle}>备注</label>
                  <input type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder="原始描述或备注" style={inputStyle} />
                </div>
              </div>

              {/* Type-specific fields card */}
              <div style={styles.card}>
                <h4 style={{ margin: '0 0 12px', fontSize: 14, color: colors.muted }}>
                  {TYPE_CONFIG.find(t => t.key === formType)?.emoji} {TYPE_CONFIG.find(t => t.key === formType)?.label}
                </h4>

                {/* ── TRADE ── */}
                {formType === 'trade' && (
                  <>
                    <div style={{ ...fieldWrap, display: 'flex', gap: 8 }}>
                      {(['buy', 'sell'] as const).map(d => (
                        <button key={d} type="button" onClick={() => setDirection(d)} style={{
                          flex: 1, padding: '8px', borderRadius: 6, border: `2px solid ${direction === d ? (d === 'buy' ? '#16a34a' : '#dc2626') : colors.border}`,
                          background: direction === d ? (d === 'buy' ? '#f0fdf4' : '#fef2f2') : 'white',
                          color: direction === d ? (d === 'buy' ? '#16a34a' : '#dc2626') : colors.muted,
                          fontWeight: 700, cursor: 'pointer', fontSize: 14,
                        }}>{d === 'buy' ? '买入' : '卖出'}</button>
                      ))}
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>资产代码 *</label>
                      <input type="text" value={assetCode} onChange={e => setAssetCode(e.target.value)} required placeholder="如 AAPL / 175" style={inputStyle} />
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>资产名称</label>
                      <input type="text" value={assetName} onChange={e => setAssetName(e.target.value)} placeholder="如 GEELY AUTOMOBILE" style={inputStyle} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>资产类型 *</label>
                        <select value={assetType} onChange={e => setAssetType(e.target.value)} style={inputStyle}>
                          {ASSET_TYPES.map(t => <option key={t}>{t}</option>)}
                        </select>
                      </div>
                      <div>
                        <label style={labelStyle}>交易所 *</label>
                        <select value={exchange} onChange={e => setExchange(e.target.value)} style={inputStyle}>
                          {EXCHANGES.map(ex => <option key={ex}>{ex}</option>)}
                        </select>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>数量 *</label>
                        <input type="number" step="any" min="0" value={quantity} onChange={e => setQuantity(e.target.value)} required placeholder="正数" style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>成交价格 *</label>
                        <input type="number" step="any" min="0" value={price} onChange={e => setPrice(e.target.value)} required style={inputStyle} />
                      </div>
                    </div>
                    {quantity && price && (
                      <div style={{ ...fieldWrap, padding: '8px 12px', borderRadius: 6, background: '#f0f9ff', fontSize: 13 }}>
                        成交金额: <strong>{(Number(quantity) * Number(price)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {currency}</strong>
                      </div>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>佣金（负数）</label>
                        <input type="number" step="any" value={commission} onChange={e => setCommission(e.target.value)} placeholder="-2.99" style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>交易税（负数）</label>
                        <input type="number" step="any" value={txFee} onChange={e => setTxFee(e.target.value)} placeholder="-34.89" style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>其他费用</label>
                        <input type="number" step="any" value={otherFee} onChange={e => setOtherFee(e.target.value)} placeholder="0" style={inputStyle} />
                      </div>
                    </div>
                    {(quantity && price) && (
                      <div style={{ padding: '8px 12px', borderRadius: 6, background: netCash() < 0 ? '#fef2f2' : '#f0fdf4', fontSize: 13, marginBottom: 14 }}>
                        净现金影响: <strong style={{ color: netCash() < 0 ? '#dc2626' : '#16a34a' }}>
                          {netCash() > 0 ? '+' : ''}{netCash().toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {currency}
                        </strong>
                      </div>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <label style={labelStyle}>已实现盈亏（卖出）</label>
                        <input type="number" step="any" value={realizedPnl} onChange={e => setRealizedPnl(e.target.value)} style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>IB成本基础（核对用）</label>
                        <input type="number" step="any" value={costBasis} onChange={e => setCostBasis(e.target.value)} style={inputStyle} />
                      </div>
                    </div>
                  </>
                )}

                {/* ── CASH ── */}
                {formType === 'cash' && (
                  <>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>类型 *</label>
                      <select value={cashSubtype} onChange={e => setCashSubtype(e.target.value)} style={inputStyle}>
                        <option value="deposit_eft">入金 - 电子转账 (EFT)</option>
                        <option value="deposit_transfer">入金 - 内部划转</option>
                        <option value="withdrawal">出金</option>
                      </select>
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>金额 *（正数）</label>
                      <input type="number" step="any" min="0" value={cashAmount} onChange={e => setCashAmount(e.target.value)} required style={inputStyle} />
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>对方账户（划转时填）</label>
                      <input type="text" value={counterpartyAccount} onChange={e => setCounterpartyAccount(e.target.value)} placeholder="如 I164167" style={inputStyle} />
                    </div>
                  </>
                )}

                {/* ── INTEREST/FEE ── */}
                {formType === 'interest' && (
                  <>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>类型 *</label>
                      <select value={interestSubtype} onChange={e => setInterestSubtype(e.target.value)} style={inputStyle}>
                        <option value="interest_debit">融资利息（支出）</option>
                        <option value="interest_credit">账户利息（收入）</option>
                        <option value="adr_fee">ADR管理费</option>
                        <option value="dividend_fee">股息手续费</option>
                        <option value="other_fee">其他费用</option>
                        <option value="adjustment">账户调整</option>
                      </select>
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>金额 *（正数，系统自动取负）</label>
                      <input type="number" step="any" min="0" value={interestAmount} onChange={e => setInterestAmount(e.target.value)} required style={inputStyle} />
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>关联资产（ADR/股息费时填）</label>
                      <input type="text" value={relatedAsset} onChange={e => setRelatedAsset(e.target.value)} placeholder="如 TAL / WB" style={inputStyle} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <label style={labelStyle}>计息起始</label>
                        <input type="date" value={accrualStart} onChange={e => setAccrualStart(e.target.value)} style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>计息截止</label>
                        <input type="date" value={accrualEnd} onChange={e => setAccrualEnd(e.target.value)} style={inputStyle} />
                      </div>
                    </div>
                  </>
                )}

                {/* ── DIVIDEND ── */}
                {formType === 'dividend' && (
                  <>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>类型 *</label>
                      <select value={divSubtype} onChange={e => setDivSubtype(e.target.value)} style={inputStyle}>
                        <option value="dividend">现金股息</option>
                        <option value="pil">替代股息 (PIL)</option>
                      </select>
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>关联资产 *</label>
                      <input type="text" value={relatedAsset} onChange={e => setRelatedAsset(e.target.value)} required placeholder="如 NTES / MOMO" style={inputStyle} />
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>股息金额 *（正数）</label>
                      <input type="number" step="any" min="0" value={divAmount} onChange={e => setDivAmount(e.target.value)} required style={inputStyle} />
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>股息手续费（如有）</label>
                      <input type="number" step="any" min="0" value={divFee} onChange={e => setDivFee(e.target.value)} placeholder="0" style={inputStyle} />
                    </div>
                  </>
                )}

                {/* ── FX ── */}
                {formType === 'fx' && (
                  <>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>卖出货币 *</label>
                        <select value={fxFromCurrency} onChange={e => setFxFromCurrency(e.target.value)} style={inputStyle}>
                          {CURRENCIES.map(c => <option key={c}>{c}</option>)}
                        </select>
                      </div>
                      <div>
                        <label style={labelStyle}>卖出金额 *（正数）</label>
                        <input type="number" step="any" min="0" value={fxFromAmount} onChange={e => setFxFromAmount(e.target.value)} required style={inputStyle} />
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>买入货币 *</label>
                        <select value={fxToCurrency} onChange={e => setFxToCurrency(e.target.value)} style={inputStyle}>
                          {CURRENCIES.map(c => <option key={c}>{c}</option>)}
                        </select>
                      </div>
                      <div>
                        <label style={labelStyle}>买入金额 *（正数）</label>
                        <input type="number" step="any" min="0" value={fxToAmount} onChange={e => setFxToAmount(e.target.value)} required style={inputStyle} />
                      </div>
                    </div>
                    {fxFromAmount && fxToAmount && (
                      <div style={{ ...fieldWrap, padding: '8px 12px', borderRadius: 6, background: '#f0f9ff', fontSize: 13 }}>
                        成交汇率: <strong>1 {fxFromCurrency} = {fxRate()} {fxToCurrency}</strong>
                      </div>
                    )}
                    <div style={fieldWrap}>
                      <label style={labelStyle}>佣金（如有，负数）</label>
                      <input type="number" step="any" value={commission} onChange={e => setCommission(e.target.value)} style={inputStyle} />
                    </div>
                  </>
                )}

                {/* ── OPTION ── */}
                {formType === 'option' && (
                  <>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>操作类型 *</label>
                      <select value={optionSubtype} onChange={e => setOptionSubtype(e.target.value)} style={inputStyle}>
                        <option value="option_buy">买入开仓</option>
                        <option value="option_sell">卖出平仓</option>
                        <option value="option_expire">期权作废</option>
                        <option value="option_exercise">期权行权</option>
                      </select>
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>期权代码</label>
                      <input type="text" value={optionCode} onChange={e => setOptionCode(e.target.value)} placeholder="如 NIO241115C4000" style={inputStyle} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>标的代码 *</label>
                        <input type="text" value={optionUnderlying} onChange={e => setOptionUnderlying(e.target.value)} required placeholder="NIO" style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>类型 *</label>
                        <select value={optionType} onChange={e => setOptionType(e.target.value as 'call' | 'put')} style={inputStyle}>
                          <option value="call">Call</option>
                          <option value="put">Put</option>
                        </select>
                      </div>
                      <div>
                        <label style={labelStyle}>合约乘数</label>
                        <input type="number" value={optionMultiplier} onChange={e => setOptionMultiplier(e.target.value)} style={inputStyle} />
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>到期日 *</label>
                        <input type="date" value={optionExpiry} onChange={e => setOptionExpiry(e.target.value)} required style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>行权价 *</label>
                        <input type="number" step="any" value={optionStrike} onChange={e => setOptionStrike(e.target.value)} required style={inputStyle} />
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                      <div>
                        <label style={labelStyle}>合约数 *</label>
                        <input type="number" min="1" value={optionQty} onChange={e => setOptionQty(e.target.value)} required style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>权利金/单价 *</label>
                        <input type="number" step="any" value={optionPremium} onChange={e => setOptionPremium(e.target.value)} required style={inputStyle} />
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <label style={labelStyle}>佣金（负数）</label>
                        <input type="number" step="any" value={commission} onChange={e => setCommission(e.target.value)} style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>监管费（负数）</label>
                        <input type="number" step="any" value={txFee} onChange={e => setTxFee(e.target.value)} style={inputStyle} />
                      </div>
                    </div>
                  </>
                )}

                {/* ── LENDING ── */}
                {formType === 'lending' && (
                  <>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>操作类型 *</label>
                      <select value={lendingSubtype} onChange={e => setLendingSubtype(e.target.value)} style={inputStyle}>
                        <option value="lending_out">新增出借</option>
                        <option value="lending_return">归还出借</option>
                        <option value="lending_income">出借收益</option>
                      </select>
                    </div>
                    {lendingSubtype !== 'lending_income' && (
                      <>
                        <div style={fieldWrap}>
                          <label style={labelStyle}>出借股票 *</label>
                          <input type="text" value={lendingAsset} onChange={e => setLendingAsset(e.target.value)} required placeholder="如 TSLA" style={inputStyle} />
                        </div>
                        <div style={fieldWrap}>
                          <label style={labelStyle}>出借数量 *</label>
                          <input type="number" step="any" min="0" value={lendingQty} onChange={e => setLendingQty(e.target.value)} required style={inputStyle} />
                        </div>
                        <div style={fieldWrap}>
                          <label style={labelStyle}>抵押金（USD）</label>
                          <input type="number" step="any" value={collateralAmount} onChange={e => setCollateralAmount(e.target.value)} style={inputStyle} />
                        </div>
                        <div style={fieldWrap}>
                          <label style={labelStyle}>出借年化利率 %</label>
                          <input type="number" step="any" value={lendingRate} onChange={e => setLendingRate(e.target.value)} placeholder="如 5.25" style={inputStyle} />
                        </div>
                      </>
                    )}
                    {lendingSubtype === 'lending_income' && (
                      <div style={fieldWrap}>
                        <label style={labelStyle}>出借收益金额 *</label>
                        <input type="number" step="any" min="0" value={cashAmount} onChange={e => setCashAmount(e.target.value)} required style={inputStyle} />
                      </div>
                    )}
                  </>
                )}

                {/* ── ACCRUAL ── */}
                {formType === 'accrual' && (
                  <>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>类型 *</label>
                      <select value={accrualSubtype} onChange={e => setAccrualSubtype(e.target.value)} style={inputStyle}>
                        <option value="interest_accrual">利息应计</option>
                        <option value="dividend_accrual">股息应计</option>
                      </select>
                    </div>
                    <div style={{ ...fieldWrap, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="checkbox" id="reversal" checked={isReversal} onChange={e => setIsReversal(e.target.checked)} />
                      <label htmlFor="reversal" style={{ fontSize: 13 }}>这是应计冲销（下期冲销上期）</label>
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>金额 *（正数，{isReversal ? '冲销为正' : '应计为负，自动处理'}）</label>
                      <input type="number" step="any" min="0" value={accrualAmount} onChange={e => setAccrualAmount(e.target.value)} required style={inputStyle} />
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>关联资产（股息应计时填）</label>
                      <input type="text" value={relatedAsset} onChange={e => setRelatedAsset(e.target.value)} placeholder="如 MOMO" style={inputStyle} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <label style={labelStyle}>计息起始</label>
                        <input type="date" value={accrualStart} onChange={e => setAccrualStart(e.target.value)} style={inputStyle} />
                      </div>
                      <div>
                        <label style={labelStyle}>计息截止</label>
                        <input type="date" value={accrualEnd} onChange={e => setAccrualEnd(e.target.value)} style={inputStyle} />
                      </div>
                    </div>
                  </>
                )}

                {/* ── CORPORATE ── */}
                {formType === 'corporate' && (
                  <>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>类型 *</label>
                      <select value={corpSubtype} onChange={e => setCorpSubtype(e.target.value)} style={inputStyle}>
                        <option value="stock_split">股票拆分</option>
                        <option value="reverse_split">反向拆分（合股）</option>
                        <option value="rights_issue">配股认购</option>
                        <option value="spinoff">分拆上市</option>
                        <option value="merger">合并收购</option>
                      </select>
                    </div>
                    <div style={fieldWrap}>
                      <label style={labelStyle}>资产代码 *</label>
                      <input type="text" value={corpAsset} onChange={e => setCorpAsset(e.target.value)} required placeholder="如 TSLA" style={inputStyle} />
                    </div>
                    {['stock_split', 'reverse_split'].includes(corpSubtype) && (
                      <div style={fieldWrap}>
                        <label style={labelStyle}>拆股比例（如5:1拆分填5.0，1:5合并填0.2）</label>
                        <input type="number" step="any" value={corpRatio} onChange={e => setCorpRatio(e.target.value)} style={inputStyle} />
                      </div>
                    )}
                    {corpSubtype === 'spinoff' && (
                      <div style={fieldWrap}>
                        <label style={labelStyle}>新股代码</label>
                        <input type="text" value={corpNewCode} onChange={e => setCorpNewCode(e.target.value)} style={inputStyle} />
                      </div>
                    )}
                    {corpSubtype === 'rights_issue' && (
                      <div style={fieldWrap}>
                        <label style={labelStyle}>配股金额（正数，系统取负）</label>
                        <input type="number" step="any" min="0" value={corpAmount} onChange={e => setCorpAmount(e.target.value)} style={inputStyle} />
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {error && <div style={{ color: '#dc2626', fontSize: 13, marginTop: 12, padding: '8px 12px', background: '#fef2f2', borderRadius: 6 }}>{error}</div>}

            <div style={{ display: 'flex', gap: 12, marginTop: 16, justifyContent: 'flex-end' }}>
              <button type="button" onClick={() => router.push('/transactions')} style={{
                padding: '10px 20px', borderRadius: 6, border: `1px solid ${colors.border}`, background: 'white', cursor: 'pointer', fontSize: 14,
              }}>取消</button>
              <button type="submit" disabled={submitting} style={{
                padding: '10px 24px', borderRadius: 6, border: 'none',
                background: submitting ? '#94a3b8' : colors.primary, color: 'white',
                cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 14,
              }}>
                {submitting ? '提交中...' : '确认提交'}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) return auth;

  try {
    const acctData = await getAccounts({ size: 100, accessToken: auth.accessToken });
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        accounts: acctData.items ?? [],
        accessToken: auth.accessToken,
      },
    };
  } catch (e: any) {
    return {
      props: {
        initialUser: auth.initialUser,
        initialLocale: auth.initialLocale,
        accounts: [],
        accessToken: auth.accessToken || '',
      },
    };
  }
}
