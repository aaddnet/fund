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

export type Account = {
  id: number;
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
  nav_date: string;
  total_assets_usd: number;
  total_shares: number;
  nav_per_share: number;
  is_locked: boolean;
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

export async function getNav(accessToken?: string | null) {
  return fetchJson<NavRecord[]>('/nav', { accessToken });
}

export async function getImportBatches(params?: { accountId?: number; accessToken?: string | null }) {
  return fetchJson<ImportBatch[]>(`/import${buildQuery({ account_id: params?.accountId })}`, { accessToken: params?.accessToken });
}

export async function getImportBatch(batchId: number, accessToken?: string | null) {
  return fetchJson<ImportBatch>(`/import/${batchId}`, { accessToken });
}

export async function getAccounts(params?: { page?: number; size?: number; holder?: string; broker?: string; q?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Account>>(`/account${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, holder: params?.holder, broker: params?.broker, q: params?.q })}`, { accessToken: params?.accessToken });
}

export async function getAccount(accountId: number, accessToken?: string | null) {
  return fetchJson<Account>(`/account/${accountId}`, { accessToken });
}

export async function getPositions(params?: { page?: number; size?: number; accountId?: number; snapshotDate?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Position>>(`/position${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 100, account_id: params?.accountId, snapshot_date: params?.snapshotDate })}`, { accessToken: params?.accessToken });
}

export async function getTransactions(params?: { page?: number; size?: number; accountId?: number; txCategory?: string; txType?: string; assetCode?: string; source?: string; dateFrom?: string; dateTo?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Transaction>>(`/transaction${buildQuery({
    page: params?.page ?? 1,
    size: params?.size ?? 100,
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

export async function createNav(payload: { nav_date: string; force?: boolean }) {
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

export async function resetImportBatch(batchId: number) {
  return fetchJson<ImportBatch>(`/import/${batchId}/reset`, { method: 'POST' });
}

export async function createAccount(payload: { holder_name?: string; broker: string; account_no: string }) {
  return fetchJson<Account>('/account', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateAccount(accountId: number, payload: { holder_name?: string | null; broker?: string | null; account_no?: string | null }) {
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

export async function getCashPositions(params?: { accountId?: number; snapshotDate?: string; accessToken?: string | null }) {
  return fetchJson<CashPosition[]>(`/cash${buildQuery({ account_id: params?.accountId, snapshot_date: params?.snapshotDate })}`, { accessToken: params?.accessToken });
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

export { API_BASE, PUBLIC_API_BASE, ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, LOCALE_COOKIE, buildQuery, fetchJson };
