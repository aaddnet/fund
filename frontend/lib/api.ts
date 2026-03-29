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

type ApiListResponse<T> = {
  items: T[];
  pagination: Pagination;
};

export type Fund = {
  id: number;
  name: string;
  base_currency: string;
  total_shares: number;
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
  client_id?: number | null;
  client_name?: string | null;
  broker: string;
  account_no: string;
  position_count: number;
  transaction_count: number;
  latest_snapshot_date?: string | null;
  latest_snapshot_value_usd?: number | null;
  latest_trade_date?: string | null;
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
  trade_date: string;
  asset_code: string;
  quantity: number;
  price: number;
  currency: string;
  tx_type: string;
  fee: number;
  import_batch_id?: number | null;
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
  imported_at?: string | null;
  preview_rows: ImportPreviewRow[];
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
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
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

export async function getImportBatches(accessToken?: string | null) {
  return fetchJson<ImportBatch[]>('/import', { accessToken });
}

export async function getImportBatch(batchId: number, accessToken?: string | null) {
  return fetchJson<ImportBatch>(`/import/${batchId}`, { accessToken });
}

export async function getFunds(page = 1, size = 50, accessToken?: string | null) {
  return fetchJson<ApiListResponse<Fund>>(`/fund${buildQuery({ page, size })}`, { accessToken });
}

export async function createFund(data: { name: string; base_currency?: string }) {
  return fetchJson<Fund>('/fund', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateFund(fundId: number, data: { name?: string; base_currency?: string }) {
  return fetchJson<Fund>(`/fund/${fundId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function getClients(params?: { page?: number; size?: number; fundId?: number; q?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Client>>(`/client${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, fund_id: params?.fundId, q: params?.q })}`, { accessToken: params?.accessToken });
}

export async function getClient(clientId: number, accessToken?: string | null) {
  return fetchJson<Client>(`/client/${clientId}`, { accessToken });
}

export async function getAccounts(params?: { page?: number; size?: number; fundId?: number; clientId?: number; broker?: string; q?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Account>>(`/account${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, fund_id: params?.fundId, client_id: params?.clientId, broker: params?.broker, q: params?.q })}`, { accessToken: params?.accessToken });
}

export async function getAccount(accountId: number, accessToken?: string | null) {
  return fetchJson<Account>(`/account/${accountId}`, { accessToken });
}

export async function getPositions(params?: { page?: number; size?: number; fundId?: number; accountId?: number; snapshotDate?: string; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Position>>(`/position${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 100, fund_id: params?.fundId, account_id: params?.accountId, snapshot_date: params?.snapshotDate })}`, { accessToken: params?.accessToken });
}

export async function getTransactions(params?: { page?: number; size?: number; fundId?: number; accountId?: number; accessToken?: string | null }) {
  return fetchJson<ApiListResponse<Transaction>>(`/transaction${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 100, fund_id: params?.fundId, account_id: params?.accountId })}`, { accessToken: params?.accessToken });
}

export async function getCustomerView(clientId: number, accessToken?: string | null) {
  return fetchJson<CustomerView>(`/customer/${clientId}`, { accessToken });
}

export async function getReportOverview(params: { periodType: string; periodValue: string; fundId?: number; clientId?: number; txType?: string; accessToken?: string | null }) {
  return fetchJson<ReportOverview>(`/reports/overview${buildQuery({ period_type: params.periodType, period_value: params.periodValue, fund_id: params.fundId, client_id: params.clientId, tx_type: params.txType })}`, { accessToken: params.accessToken });
}

export async function uploadImportBatch(payload: { source: string; accountId: number; file: File }) {
  const formData = new FormData();
  formData.append('source', payload.source);
  formData.append('account_id', String(payload.accountId));
  formData.append('file', payload.file);
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

export async function createNav(payload: { fund_id: number; nav_date: string }) {
  return fetchJson<NavRecord>('/nav/calc', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteNav(navId: number) {
  return fetchJson<void>(`/nav/${navId}`, { method: 'DELETE' });
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

export async function createAccount(payload: { fund_id: number; client_id: number; broker: string; account_no: string }) {
  return fetchJson<Account>('/account', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateAccount(accountId: number, payload: { fund_id?: number | null; client_id?: number | null; broker?: string | null; account_no?: string | null }) {
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

export { API_BASE, PUBLIC_API_BASE, ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, LOCALE_COOKIE, buildQuery, fetchJson };
