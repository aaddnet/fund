import type { GetServerSidePropsContext } from 'next';

const BROWSER_API_BASE = process.env.NEXT_PUBLIC_API || 'http://127.0.0.1:8000';
const SERVER_API_BASE = process.env.INTERNAL_API_BASE || process.env.NEXT_PUBLIC_API || 'http://127.0.0.1:8000';
const API_BASE = typeof window === 'undefined' ? SERVER_API_BASE : BROWSER_API_BASE;
// 用于前端界面展示的地址必须保持 SSR/客户端一致，避免 hydration mismatch。
const PUBLIC_API_BASE = BROWSER_API_BASE;
const ACCESS_TOKEN_COOKIE = 'invest_access_token';
const REFRESH_TOKEN_COOKIE = 'invest_refresh_token';
const LOCALE_COOKIE = 'invest_locale';

export type Locale = 'en' | 'zh';

export type AuthUser = {
  id: number;
  username: string;
  role: string;
  permissions: string[];
  client_scope_id?: number | null;
  display_name?: string | null;
  is_active: boolean;
  last_login_at?: string | null;
  password_changed_at?: string | null;
  failed_login_attempts?: number;
  locked_until?: string | null;
};

export type AuthSessionResponse = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_at: string;
  refresh_expires_at: string;
  user: AuthUser;
};

type Pagination = {
  page: number;
  size: number;
  total: number;
};

export type ApiListResponse<T> = {
  items: T[];
  pagination: Pagination;
};

export type Fund = {
  id: number;
  name: string;
  base_currency: string;
  total_shares: number;
  fund_code?: string | null;
  inception_date?: string | null;
  first_capital_date?: string | null;
  fund_type?: string | null;
  status?: string | null;
  hurdle_rate?: number | null;
  perf_fee_rate?: number | null;
  perf_fee_frequency?: string | null;
  subscription_cycle?: string | null;
  nav_decimal?: number;
  share_decimal?: number;
  description?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CashPosition = {
  id: number;
  account_id: number;
  currency: string;
  amount: number;
  snapshot_date: string;
  note?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ShareRegisterEntry = {
  id: number;
  fund_id: number;
  client_id: number;
  event_date: string;
  event_type: string;
  shares_delta: number;
  shares_after: number;
  nav_per_share: number;
  amount_usd?: number | null;
  ref_share_tx_id?: number | null;
  note?: string | null;
  created_at?: string | null;
};

export type CapitalAccount = {
  id: number;
  fund_id: number;
  client_id: number;
  total_invested_usd: number;
  total_redeemed_usd: number;
  avg_cost_nav?: number | null;
  current_shares: number;
  unrealized_pnl_usd?: number | null;
  last_updated_date?: string | null;
};

export type Client = {
  id: number;
  name: string;
  email?: string | null;
  account_count?: number;
  fund_count?: number;
  fund_ids?: number[];
  total_share_balance?: number;
  total_holding_value_usd?: number | null;
  holding_currency?: string | null;
  share_tx_count?: number;
  latest_trade_date?: string | null;
  latest_share_tx_date?: string | null;
};

export type Account = {
  id: number;
  fund_id: number;
  fund_name?: string | null;
  holder_name?: string | null;
  broker: string;
  account_no: string;
  position_count: number;
  transaction_count: number;
  latest_snapshot_date?: string | null;
  latest_snapshot_value_usd?: number | null;
  latest_trade_date?: string | null;
  // V4.1: IB multi-currency margin account fields
  base_currency?: string | null;
  account_capabilities?: string | null;
  is_margin?: boolean | null;
  master_account_no?: string | null;
  ib_account_no?: string | null;
};

export type Position = {
  id: number;
  account_id: number;
  asset_code: string;
  quantity: number;
  average_cost?: number | null;
  currency: string;
  snapshot_date: string;
};

export type Transaction = {
  id: number;
  account_id: number;
  // Classification
  tx_category: string;      // EQUITY / CASH / FX / MARGIN / CORPORATE
  tx_type: string;
  source: string;           // manual / pdf_import / csv_import / migration
  // Timing
  trade_date: string;
  settle_date?: string | null;
  // Core
  currency: string;
  amount?: number | null;
  fee: number;
  description?: string | null;
  // EQUITY fields
  asset_code?: string | null;
  asset_name?: string | null;
  asset_type?: string | null;
  quantity?: number | null;
  price?: number | null;
  realized_pnl?: number | null;
  // Option fields
  option_underlying?: string | null;
  option_expiry?: string | null;
  option_strike?: number | null;
  option_type?: string | null;      // call / put
  option_multiplier?: number | null;
  // FX fields
  fx_from_currency?: string | null;
  fx_from_amount?: number | null;
  fx_to_currency?: string | null;
  fx_to_amount?: number | null;
  fx_rate?: number | null;
  fx_pnl?: number | null;
  // Corporate action fields
  corporate_ratio?: number | null;
  corporate_ref_code?: string | null;
  // V4.1: subtype + fee decomposition
  tx_subtype?: string | null;
  gross_amount?: number | null;
  commission?: number | null;
  transaction_fee?: number | null;
  other_fee?: number | null;
  // V4.1: asset metadata
  isin?: string | null;
  exchange?: string | null;
  multiplier?: number | null;
  close_price?: number | null;
  cost_basis?: number | null;
  // V4.1: securities lending
  lending_counterparty?: string | null;
  lending_rate?: number | null;
  collateral_amount?: number | null;
  // V4.1: accruals
  accrual_type?: string | null;
  accrual_period_start?: string | null;
  accrual_period_end?: string | null;
  accrual_reversal_id?: number | null;
  // V4.1: internal transfer
  counterparty_account?: string | null;
  // V4.2: lending detail
  lending_asset_code?: string | null;
  lending_quantity?: number | null;
  lending_rate_pct?: number | null;
  // V4.2: accrual reversal flag
  is_accrual_reversal?: boolean | null;
  // V4.2: corporate new code
  corporate_new_code?: string | null;
  // Metadata
  import_batch_id?: number | null;
  created_by?: number | null;
  updated_by?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type TransactionCreateRequest = {
  account_id: number;
  tx_category: string;
  tx_type: string;
  trade_date: string;
  currency: string;
  settle_date?: string | null;
  description?: string | null;
  source?: string;
  gross_amount?: number | null;
  commission?: number | null;
  transaction_fee?: number | null;
  other_fee?: number | null;
  amount?: number | null;
  fee?: number | null;
  asset_code?: string | null;
  asset_name?: string | null;
  asset_type?: string | null;
  exchange?: string | null;
  isin?: string | null;
  quantity?: number | null;
  price?: number | null;
  realized_pnl?: number | null;
  cost_basis?: number | null;
  option_underlying?: string | null;
  option_expiry?: string | null;
  option_strike?: number | null;
  option_type?: string | null;
  option_multiplier?: number | null;
  fx_from_currency?: string | null;
  fx_from_amount?: number | null;
  fx_to_currency?: string | null;
  fx_to_amount?: number | null;
  fx_rate?: number | null;
  lending_asset_code?: string | null;
  lending_quantity?: number | null;
  lending_rate_pct?: number | null;
  collateral_amount?: number | null;
  accrual_type?: string | null;
  accrual_period_start?: string | null;
  accrual_period_end?: string | null;
  is_accrual_reversal?: boolean | null;
  corporate_ratio?: number | null;
  corporate_new_code?: string | null;
  counterparty_account?: string | null;
  tx_subtype?: string | null;
};

export type FXSummary = {
  from_currency: string;
  to_currency: string;
  total_from: number;
  total_to: number;
  avg_rate: number;
  total_fee_usd: number;
  realized_pnl_usd: number;
};

export type CashLedgerEvent = {
  tx_id: number;
  trade_date: string;
  settle_date?: string | null;
  tx_category: string;
  tx_type: string;
  description?: string | null;
  delta: number;
  balance_after: number;
};

export type CashBalances = {
  account_id: number;
  as_of_date: string;
  balances: Record<string, number>;
};

export type NavRecord = {
  id: number;
  fund_id: number;
  fund_name?: string | null;
  nav_date: string;
  total_assets_usd: number;
  total_shares: number;
  nav_per_share: number;
  is_locked: boolean;
};

export type ShareTransaction = {
  id: number;
  fund_id: number;
  client_id: number;
  tx_date: string;
  tx_type: string;
  amount_usd: number;
  shares: number;
  nav_at_date: number;
};

export type ShareBalance = {
  fund_id: number;
  client_id: number;
  share_balance: number;
};

export type FeeRecord = {
  id: number;
  fund_id: number;
  fee_date: string;
  gross_return: number;
  fee_rate: number;
  fee_amount_usd: number;
  nav_start?: number | null;
  nav_end_before_fee?: number | null;
  annual_return_pct?: number | null;
  excess_return_pct?: number | null;
  fee_base_usd?: number | null;
  nav_after_fee?: number | null;
  applied_date?: string | null;
};

export type ImportPreviewRow = {
  row_number: number;
  trade_date: string;
  asset_code: string;
  quantity: string;
  price: string;
  currency: string;
  tx_type: string;
  fee: string;
  snapshot_date: string;
};

export type PendingDeposit = {
  date: string;
  amount_usd: number;
  tx_type: string;
  currency: string;
  note: string;
  confirmed_as?: string;
};

export type ImportOverlap = {
  overlap_count: number;
  min_date: string;
  max_date: string;
};

// V4.1: NAV Breakdown types
export type NavBreakdownPosition = {
  asset_code: string;
  asset_type?: string | null;
  quantity: number;
  currency: string;
  average_cost: number;
  estimated_value: number;
  estimated_value_usd: number;
};

export type NavBreakdownAccrual = {
  id: number;
  accrual_type: string;
  currency: string;
  amount: number;
  accrual_date: string;
  expected_pay_date?: string | null;
  asset_code?: string | null;
  is_reversed: boolean;
};

export type NavBreakdownLendingPosition = {
  id: number;
  asset_code: string;
  quantity_lent: number;
  collateral_usd?: number | null;
  lending_rate?: number | null;
  start_date: string;
  end_date?: string | null;
};

export type NavBreakdown = {
  account_id: number;
  as_of_date: string;
  stock_value: {
    positions: NavBreakdownPosition[];
    total_cost_usd: number;
  };
  cash: {
    balances: Record<string, number>;
    total_usd: number;
  };
  accruals: {
    items: NavBreakdownAccrual[];
    total_usd: number;
  };
  securities_lending: {
    positions: NavBreakdownLendingPosition[];
    net_usd: number;
    income_ytd: number;
  };
  total_nav_usd: number;
};

export type ImportBatch = {
  id: number;
  source: string;
  filename: string;
  account_id: number;
  status: string;
  row_count: number;
  parsed_count: number;
  confirmed_count: number;
  failed_reason?: string | null;
  overlap?: ImportOverlap | null;   // set when existing transactions found in same date range
  imported_at?: string | null;
  preview_rows: ImportPreviewRow[];
  pending_deposits?: PendingDeposit[];
};

export type CustomerView = {
  client: Client;
  accounts: Account[];
  share_balances: ShareBalance[];
  share_history: ShareTransaction[];
  nav_history: NavRecord[];
};

export type ReportBreakdownRow = {
  key: string | number;
  share_tx_count: number;
  subscription_amount_usd: number;
  redemption_amount_usd: number;
  net_share_flow_usd: number;
  shares_delta: number;
  latest_tx_date?: string | null;
};

export type ReportTransactionAssetRow = {
  asset_code: string;
  transaction_count: number;
  gross_notional_estimate: number;
  latest_trade_date?: string | null;
};

export type ReportNavByFundRow = {
  fund_id: number;
  latest_nav_date?: string | null;
  latest_nav_per_share: number;
  latest_total_assets_usd: number;
  record_count: number;
};

export type ReportShareFlowSeriesRow = {
  date: string;
  subscription_amount_usd: number;
  redemption_amount_usd: number;
  net_share_flow_usd: number;
  share_tx_count: number;
};

export type ReportNavSeriesRow = {
  date: string;
  fund_id: number;
  nav_per_share: number;
  total_assets_usd: number;
};

export type ReportOverview = {
  filters: {
    period_type: 'month' | 'quarter' | 'year' | string;
    period_value: string;
    date_from: string;
    date_to: string;
    fund_id?: number | null;
    client_id?: number | null;
    tx_type?: string | null;
  };
  summary: {
    share_tx_count: number;
    subscription_amount_usd: number;
    redemption_amount_usd: number;
    net_share_flow_usd: number;
    nav_record_count: number;
    fee_record_count: number;
    transaction_count: number;
    fund_count: number;
    client_count: number;
    avg_nav_per_share: number;
    latest_nav_date?: string | null;
  };
  share_history: ShareTransaction[];
  nav_records: NavRecord[];
  fee_records: FeeRecord[];
  transactions: Transaction[];
  breakdowns: {
    by_fund: ReportBreakdownRow[];
    by_client: ReportBreakdownRow[];
    by_tx_type: ReportBreakdownRow[];
    transactions_by_asset: ReportTransactionAssetRow[];
    nav_by_fund: ReportNavByFundRow[];
  };
  series: {
    share_flow_by_date: ReportShareFlowSeriesRow[];
    nav_trend: ReportNavSeriesRow[];
  };
};

type FetchOptions = RequestInit & {
  accessToken?: string | null;
};

function parseCookieString(cookieHeader: string | undefined): Record<string, string> {
  return (cookieHeader || '').split(';').reduce<Record<string, string>>((acc, item) => {
    const [key, ...rest] = item.trim().split('=');
    if (!key) return acc;
    acc[key] = decodeURIComponent(rest.join('='));
    return acc;
  }, {});
}

export function getServerAccessToken(context?: GetServerSidePropsContext): string | null {
  return parseCookieString(context?.req?.headers?.cookie)[ACCESS_TOKEN_COOKIE] || null;
}

export function getServerRefreshToken(context?: GetServerSidePropsContext): string | null {
  return parseCookieString(context?.req?.headers?.cookie)[REFRESH_TOKEN_COOKIE] || null;
}

export function getServerLocale(context?: GetServerSidePropsContext): Locale {
  const locale = parseCookieString(context?.req?.headers?.cookie)[LOCALE_COOKIE];
  return locale === 'zh' ? 'zh' : 'en';
}

function getBrowserAccessToken(): string | null {
  if (typeof document === 'undefined') return null;
  return parseCookieString(document.cookie)[ACCESS_TOKEN_COOKIE] || null;
}

function getAuthHeader(accessToken?: string | null): string | null {
  const resolved = accessToken ?? getBrowserAccessToken();
  return resolved ? `Bearer ${resolved}` : null;
}

async function fetchJson<T>(path: string, init?: FetchOptions): Promise<T> {
  const headers = new Headers(init?.headers || {});
  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const authorization = getAuthHeader(init?.accessToken);
  if (authorization && !headers.has('Authorization')) {
    headers.set('Authorization', authorization);
  }

  let response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (response.status === 401 && typeof window !== 'undefined' && !init?.accessToken && path !== '/auth/login' && path !== '/auth/refresh') {
    const refreshToken = parseCookieString(document.cookie)[REFRESH_TOKEN_COOKIE];
    if (refreshToken) {
      try {
        const nextSession = await refreshSession(refreshToken);
        persistSessionCookies(nextSession);
        headers.set('Authorization', `Bearer ${nextSession.access_token}`);
        response = await fetch(`${API_BASE}${path}`, {
          ...init,
          headers,
        });
      } catch {
        clearSessionCookies();
      }
    }
  }

  if (!response.ok) {
    let message = `API ${path} failed with ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = (body.detail as Array<{ msg?: string }>).map(e => e.msg || JSON.stringify(e)).join('; ');
      } else if (body.detail) {
        message = JSON.stringify(body.detail);
      } else {
        message = JSON.stringify(body);
      }
    } catch {
      const text = await response.text();
      if (text) {
        message = text;
      }
    }
    const error = new Error(message) as Error & { status?: number; detail?: unknown };
    error.status = response.status;
    try { error.detail = JSON.parse(message); } catch { /* message is plain string */ }
    throw error;
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

function buildQuery(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value));
    }
  });
  const suffix = query.toString();
  return suffix ? `?${suffix}` : '';
}

export async function login(payload: { username: string; password: string }) {
  const formData = new URLSearchParams();
  formData.set('username', payload.username);
  formData.set('password', payload.password);
  return fetchJson<AuthSessionResponse>('/auth/login', {
    method: 'POST',
    body: formData,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}

export async function refreshSession(refreshToken: string) {
  const formData = new URLSearchParams();
  formData.set('refresh_token', refreshToken);
  return fetchJson<AuthSessionResponse>('/auth/refresh', {
    method: 'POST',
    body: formData,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}

export async function getMe(accessToken?: string | null) {
  return fetchJson<{ actor: { role: string; operator_id: string; client_scope_id?: number | null; auth_mode: string; session_id?: number | null; username?: string | null; permissions: string[] }; user: AuthUser | null }>('/auth/me', { accessToken });
}

export async function logout(accessToken?: string | null) {
  return fetchJson<void>('/auth/logout', {
    method: 'POST',
    accessToken,
  });
}

export function buildSessionCookies(session: AuthSessionResponse) {
  const secure = typeof window !== 'undefined' && window.location.protocol === 'https:' ? '; Secure' : '';
  return [
    `${ACCESS_TOKEN_COOKIE}=${encodeURIComponent(session.access_token)}; path=/; SameSite=Strict${secure}`,
    `${REFRESH_TOKEN_COOKIE}=${encodeURIComponent(session.refresh_token)}; path=/; SameSite=Strict${secure}`,
  ];
}

export function clearSessionCookies() {
  if (typeof document === 'undefined') return;
  document.cookie = `${ACCESS_TOKEN_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Strict`;
  document.cookie = `${REFRESH_TOKEN_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Strict`;
}

export function persistSessionCookies(session: AuthSessionResponse) {
  if (typeof document === 'undefined') return;
  buildSessionCookies(session).forEach((cookie) => {
    document.cookie = cookie;
  });
}

export function persistLocaleCookie(locale: Locale) {
  if (typeof document === 'undefined') return;
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; SameSite=Lax`;
}

export async function getHealth(accessToken?: string | null) {
  return fetchJson<{ status: string; uptime_seconds?: number }>('/health', { accessToken });
}

export async function getHealthDb(accessToken?: string | null) {
  return fetchJson<{ db: string }>('/health/db', { accessToken });
}

export async function getNav(fundId?: number, accessToken?: string | null) {
  return fetchJson<NavRecord[]>(`/nav${buildQuery({ fund_id: fundId })}`, { accessToken });
}

export async function getShareHistory(params?: { fundId?: number; clientId?: number; txType?: string; dateFrom?: string; dateTo?: string; accessToken?: string | null }) {
  return fetchJson<ShareTransaction[]>(`/share/history${buildQuery({ fund_id: params?.fundId, client_id: params?.clientId, tx_type: params?.txType, date_from: params?.dateFrom, date_to: params?.dateTo })}`, { accessToken: params?.accessToken });
}

export async function getShareBalances(params?: { fundId?: number; clientId?: number; accessToken?: string | null }) {
  return fetchJson<ShareBalance[]>(`/share/balances${buildQuery({ fund_id: params?.fundId, client_id: params?.clientId })}`, { accessToken: params?.accessToken });
}

export async function getFees(accessToken?: string | null) {
  return fetchJson<FeeRecord[]>('/fee', { accessToken });
}

export async function getImportBatches(params?: { accountId?: number; accessToken?: string | null }) {
  return fetchJson<ImportBatch[]>(`/import${buildQuery({ account_id: params?.accountId })}`, { accessToken: params?.accessToken });
}

export async function getImportBatch(batchId: number, accessToken?: string | null) {
  return fetchJson<ImportBatch>(`/import/${batchId}`, { accessToken });
}

export async function getFunds(page = 1, size = 50, accessToken?: string | null) {
  return fetchJson<ApiListResponse<Fund>>(`/fund${buildQuery({ page, size })}`, { accessToken });
}

export async function createFund(data: { name: string; base_currency?: string; total_shares?: number }) {
  return fetchJson<Fund>('/fund', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateFund(fundId: number, data: { name?: string; base_currency?: string; total_shares?: number; [key: string]: any }) {
  return fetchJson<Fund>(`/fund/${fundId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function getClients(params?: { page?: number; size?: number; fundId?: number; q?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Client>>(`/client${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, fund_id: params?.fundId, q: params?.q })}`, { accessToken: params?.accessToken });
}

export async function getClient(clientId: number, accessToken?: string | null) {
  return fetchJson<Client>(`/client/${clientId}`, { accessToken });
}

export async function getAccounts(params?: { page?: number; size?: number; fundId?: number; holder?: string; broker?: string; q?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Account>>(`/account${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, fund_id: params?.fundId, holder: params?.holder, broker: params?.broker, q: params?.q })}`, { accessToken: params?.accessToken });
}

export async function getAccount(accountId: number, accessToken?: string | null) {
  return fetchJson<Account>(`/account/${accountId}`, { accessToken });
}

export async function getPositions(params?: { page?: number; size?: number; fundId?: number; accountId?: number; snapshotDate?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Position>>(`/position${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 100, fund_id: params?.fundId, account_id: params?.accountId, snapshot_date: params?.snapshotDate })}`, { accessToken: params?.accessToken });
}

export async function getTransactions(params?: { page?: number; size?: number; fundId?: number; accountId?: number; txCategory?: string; txType?: string; assetCode?: string; source?: string; dateFrom?: string; dateTo?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Transaction>>(`/transaction${buildQuery({
    page: params?.page ?? 1,
    size: params?.size ?? 100,
    fund_id: params?.fundId,
    account_id: params?.accountId,
    tx_category: params?.txCategory,
    tx_type: params?.txType,
    asset_code: params?.assetCode,
    source: params?.source,
    date_from: params?.dateFrom,
    date_to: params?.dateTo,
  })}`, { accessToken: params?.accessToken });
}

export async function createTransaction(data: TransactionCreateRequest, accessToken?: string | null) {
  return fetchJson<Transaction>('/transaction', { method: 'POST', body: JSON.stringify(data), accessToken });
}

export async function updateTransaction(id: number, data: Partial<TransactionCreateRequest>, accessToken?: string | null) {
  return fetchJson<Transaction>(`/transaction/${id}`, { method: 'PATCH', body: JSON.stringify(data), accessToken });
}

export async function deleteTransaction(id: number, accessToken?: string | null) {
  return fetchJson<{ status: string; id: number }>(`/transaction/${id}`, { method: 'DELETE', accessToken });
}

export async function getCustomerView(clientId: number, accessToken?: string | null) {
  return fetchJson<CustomerView>(`/customer/${clientId}`, { accessToken });
}

export async function getReportOverview(params: { periodType: string; periodValue: string; fundId?: number; clientId?: number; txType?: string; accessToken?: string | null }) {
  return fetchJson<ReportOverview>(`/reports/overview${buildQuery({ period_type: params.periodType, period_value: params.periodValue, fund_id: params.fundId, client_id: params.clientId, tx_type: params.txType })}`, { accessToken: params.accessToken });
}

export async function uploadImportBatch(payload: { source: string; accountId: number; file: File; force?: boolean }) {
  const formData = new FormData();
  formData.append('source', payload.source);
  formData.append('account_id', String(payload.accountId));
  formData.append('file', payload.file);
  if (payload.force) formData.append('force', 'true');
  return fetchJson<ImportBatch>('/import/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function confirmImportBatch(batchId: number) {
  return fetchJson<ImportBatch>(`/import/${batchId}/confirm`, {
    method: 'POST',
  });
}

export async function createNav(payload: { fund_id: number; nav_date: string; force?: boolean }) {
  return fetchJson<NavRecord>('/nav/calc', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteNav(navId: number) {
  return fetchJson<void>(`/nav/${navId}`, { method: 'DELETE' });
}

export async function getPendingDeposits(batchId: number): Promise<PendingDeposit[]> {
  return fetchJson<PendingDeposit[]>(`/import/${batchId}/pending-deposits`);
}

export async function confirmDeposit(batchId: number, payload: { deposit_index: number; client_id?: number | null; confirm_as: string; note?: string }) {
  return fetchJson<ImportBatch>(`/import/${batchId}/confirm-deposit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function resetImportBatch(batchId: number) {
  return fetchJson<ImportBatch>(`/import/${batchId}/reset`, { method: 'POST' });
}

export type NavRebuildResult = {
  date: string;
  nav_per_share?: number;
  total_assets_usd?: number;
  status: string;
  msg?: string;
};

export async function rebuildNavBatch(payload: { fund_id: number; start_date: string; end_date: string; frequency: string; force?: boolean }) {
  return fetchJson<{ fund_id: number; results: NavRebuildResult[] }>('/nav/rebuild-batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createShareSubscription(payload: { fund_id: number; client_id: number; tx_date: string; amount_usd: number }) {
  return fetchJson<ShareTransaction>('/share/subscribe', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createShareRedemption(payload: { fund_id: number; client_id: number; tx_date: string; amount_usd: number }) {
  return fetchJson<ShareTransaction>('/share/redeem', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateShareTransaction(txId: number, data: Record<string, any>) {
  return fetchJson<ShareTransaction>(`/share/transaction/${txId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function deleteShareTransaction(txId: number) {
  return fetchJson<void>(`/share/transaction/${txId}`, { method: 'DELETE' });
}

export async function createClient(payload: { name: string; email?: string | null }) {
  return fetchJson<Client>('/client', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateClient(clientId: number, payload: { name?: string | null; email?: string | null }) {
  return fetchJson<Client>(`/client/${clientId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function createAccount(payload: { fund_id: number; holder_name?: string; broker: string; account_no: string }) {
  return fetchJson<Account>('/account', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateAccount(accountId: number, payload: { fund_id?: number | null; holder_name?: string | null; broker?: string | null; account_no?: string | null }) {
  return fetchJson<Account>(`/account/${accountId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function listAuthUsers(accessToken?: string | null) {
  return fetchJson<AuthUser[]>('/auth/users', { accessToken });
}

export async function createAuthUser(data: { username: string; password: string; role: string; display_name?: string | null; client_scope_id?: number | null; is_active?: boolean }) {
  return fetchJson<AuthUser>('/auth/users', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateAuthUser(userId: number, data: { role?: string | null; display_name?: string | null; client_scope_id?: number | null; is_active?: boolean | null }) {
  return fetchJson<AuthUser>(`/auth/users/${userId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function resetAuthUserPassword(userId: number, newPassword: string) {
  return fetchJson<AuthUser>(`/auth/users/${userId}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password: newPassword }) });
}

export async function unlockAuthUser(userId: number) {
  return fetchJson<{ id: number; username: string; locked_until: null; failed_login_attempts: number }>(`/auth/users/${userId}/unlock`, { method: 'POST' });
}

export async function changeMyPassword(data: { current_password: string; new_password: string }) {
  return fetchJson<AuthUser>('/auth/me/password', { method: 'PATCH', body: JSON.stringify(data) });
}

export async function getCashPositions(params?: { fundId?: number; accountId?: number; snapshotDate?: string; accessToken?: string | null }) {
  return fetchJson<CashPosition[]>(`/cash${buildQuery({ fund_id: params?.fundId, account_id: params?.accountId, snapshot_date: params?.snapshotDate })}`, { accessToken: params?.accessToken });
}

export async function upsertCashPosition(payload: { account_id: number; currency: string; amount: number; snapshot_date: string; note?: string | null }) {
  return fetchJson<CashPosition>('/cash', { method: 'POST', body: JSON.stringify(payload) });
}

export async function deleteCashPosition(cashId: number) {
  return fetchJson<void>(`/cash/${cashId}`, { method: 'DELETE' });
}

// --- V4: FX transactions & cash ledger ---

export async function createFxTransaction(payload: {
  account_id: number;
  trade_date: string;
  fx_from_currency: string;
  fx_from_amount: number;
  fx_to_currency: string;
  fx_to_amount: number;
  fee?: number;
  fee_currency?: string;
  description?: string;
}) {
  return fetchJson<Transaction>('/transaction/fx', { method: 'POST', body: JSON.stringify(payload) });
}

export async function getCashLedger(accountId: number, currency: string, accessToken?: string | null) {
  return fetchJson<{ account_id: number; currency: string; events: CashLedgerEvent[] }>(
    `/accounts/${accountId}/cash-ledger?currency=${encodeURIComponent(currency)}`,
    { accessToken },
  );
}

export async function getCashBalances(accountId: number, asOfDate?: string, accessToken?: string | null) {
  const q = asOfDate ? `?as_of_date=${asOfDate}` : '';
  return fetchJson<CashBalances>(`/accounts/${accountId}/cash-balances${q}`, { accessToken });
}

export async function getFxSummary(accountId: number, accessToken?: string | null) {
  return fetchJson<{ account_id: number; fx_trades: FXSummary[] }>(
    `/accounts/${accountId}/fx-summary`,
    { accessToken },
  );
}

// V4.1: NAV Breakdown
export async function getNavBreakdown(accountId: number, asOfDate?: string, accessToken?: string | null) {
  const q = asOfDate ? `?as_of_date=${asOfDate}` : '';
  return fetchJson<NavBreakdown>(`/account/${accountId}/nav-breakdown${q}`, { accessToken });
}

export async function getShareRegister(params?: { fundId?: number; clientId?: number; accessToken?: string | null }) {
  return fetchJson<ShareRegisterEntry[]>(`/share/register${buildQuery({ fund_id: params?.fundId, client_id: params?.clientId })}`, { accessToken: params?.accessToken });
}

export async function updateShareRegisterEntry(entryId: number, data: Record<string, any>) {
  return fetchJson<ShareRegisterEntry>(`/share/register/${entryId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function deleteShareRegisterEntry(entryId: number) {
  return fetchJson<void>(`/share/register/${entryId}`, { method: 'DELETE' });
}

export async function getClientCapitalAccounts(clientId: number, accessToken?: string | null) {
  return fetchJson<CapitalAccount[]>(`/client/${clientId}/capital-account`, { accessToken });
}

export async function createSeedCapital(fundId: number, payload: { client_id?: number; amount_usd: number; seed_date: string; shares_override?: number }) {
  return fetchJson<{ fund_id: number; client_id: number | null; shares_issued: number; nav_per_share: number; amount_usd: number; seed_date: string }>(`/fund/${fundId}/seed`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function activateFund(fundId: number) {
  return fetchJson<Fund>(`/fund/${fundId}/activate`, { method: 'POST' });
}

// --- Exchange Rate ---

export type ExchangeRate = {
  id: number;
  base_currency: string;
  quote_currency: string;
  rate: number;
  snapshot_date: string;
  source?: string | null;
};

export async function getRates(params?: { page?: number; size?: number; base?: string; quote?: string; snapshot_date?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<ExchangeRate>>(`/rates${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, base: params?.base, quote: params?.quote, snapshot_date: params?.snapshot_date })}`, { accessToken: params?.accessToken });
}

export async function upsertRateManual(payload: { base: string; quote: string; rate: number; snapshot_date: string }) {
  return fetchJson<ExchangeRate>('/rates/manual', { method: 'POST', body: JSON.stringify(payload) });
}

export async function fetchRateFromApi(payload: { base: string; quote: string; snapshot_date: string }) {
  return fetchJson<ExchangeRate>('/rates/fetch', { method: 'POST', body: JSON.stringify(payload) });
}

export async function importRatesCsv(file: File) {
  const fd = new FormData();
  fd.append('file', file);
  return fetchJson<{ imported: number }>('/rates/csv', { method: 'POST', body: fd });
}

export async function checkNavRates(fundId: number, navDate: string, accessToken?: string | null) {
  return fetchJson<{ ready: boolean; missing_rates: string[]; assets_affected: string[] }>(`/nav/check-rates${buildQuery({ fund_id: fundId, nav_date: navDate })}`, { accessToken });
}

// --- Asset Price ---

export type AssetPrice = {
  id: number;
  asset_code: string;
  price_usd: number;
  source: string;
  snapshot_date: string;
};

export async function getPrices(params?: { page?: number; size?: number; asset_code?: string; snapshot_date?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<AssetPrice>>(`/price${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, asset_code: params?.asset_code, snapshot_date: params?.snapshot_date })}`, { accessToken: params?.accessToken });
}

export async function upsertPriceManual(payload: { asset_code: string; price_usd: number; snapshot_date: string }) {
  return fetchJson<AssetPrice>('/price/manual', { method: 'POST', body: JSON.stringify(payload) });
}

export async function importPricesCsv(file: File) {
  const fd = new FormData();
  fd.append('file', file);
  return fetchJson<{ imported: number }>('/price/csv', { method: 'POST', body: fd });
}

// --- PDF Import ---

export type ValidationItem = {
  asset_code: string;
  ai_quantity: number;
  db_quantity?: number;
  diff_pct?: number;
  level: 'error' | 'warning' | 'new';
};

export type ValidationResult = {
  errors: ValidationItem[];
  warnings: ValidationItem[];
  new_positions: ValidationItem[];
  can_auto_confirm: boolean;
  summary: { total: number; matched: number; warnings: number; errors: number; new: number };
};

export type PdfImportBatchRecord = {
  id: number;
  account_id: number;
  snapshot_date: string;
  filename?: string | null;
  status: string;
  failed_reason?: string | null;
  ai_model?: string | null;
  parsed_data?: Record<string, any>;
  confirmed_data?: Record<string, any>;
  pending_deposits?: any[];
  validation?: ValidationResult | null;
  created_at?: string | null;
};

export async function listPdfBatches(params?: { accountId?: number; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<PdfImportBatchRecord>>(`/pdf-import${buildQuery({ account_id: params?.accountId, size: 100 })}`, { accessToken: params?.accessToken });
}

export async function getPdfBatch(batchId: number, accessToken?: string | null) {
  return fetchJson<PdfImportBatchRecord>(`/pdf-import/${batchId}`, { accessToken });
}

export async function uploadPdfBatch(payload: { accountId: number; snapshotDate: string; file: File }) {
  const fd = new FormData();
  fd.append('account_id', String(payload.accountId));
  fd.append('snapshot_date', payload.snapshotDate);
  fd.append('file', payload.file);
  return fetchJson<PdfImportBatchRecord>('/pdf-import/upload', { method: 'POST', body: fd });
}

export async function confirmPdfBatch(batchId: number, confirmedData?: Record<string, any>) {
  return fetchJson<PdfImportBatchRecord>(`/pdf-import/${batchId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ confirmed_data: confirmedData ?? null }),
  });
}

export async function resetPdfBatch(batchId: number) {
  return fetchJson<PdfImportBatchRecord>(`/pdf-import/${batchId}`, { method: 'DELETE' });
}

// --- SHR-02: Share transaction undo ---

export async function deleteShareTx(shareTxId: number) {
  return fetchJson<{ deleted: boolean }>(`/shares/${shareTxId}`, { method: 'DELETE' });
}

export { API_BASE, PUBLIC_API_BASE, ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, LOCALE_COOKIE, buildQuery, fetchJson };
