const API_BASE = process.env.NEXT_PUBLIC_API || 'http://127.0.0.1:8000';

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
};

export type Account = {
  id: number;
  fund_id: number;
  client_id?: number | null;
  broker: string;
  account_no: string;
  position_count: number;
  transaction_count: number;
  latest_snapshot_date?: string | null;
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

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {});
  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let message = `API ${path} failed with ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || JSON.stringify(body);
    } catch {
      const text = await response.text();
      if (text) {
        message = text;
      }
    }
    throw new Error(message);
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

export async function getHealth() {
  return fetchJson<{ status: string }>('/health');
}

export async function getHealthDb() {
  return fetchJson<{ db: string }>('/health/db');
}

export async function getNav(fundId?: number) {
  return fetchJson<NavRecord[]>(`/nav${buildQuery({ fund_id: fundId })}`);
}

export async function getShareHistory(params?: { fundId?: number; clientId?: number; txType?: string; dateFrom?: string; dateTo?: string }) {
  return fetchJson<ShareTransaction[]>(`/share/history${buildQuery({ fund_id: params?.fundId, client_id: params?.clientId, tx_type: params?.txType, date_from: params?.dateFrom, date_to: params?.dateTo })}`);
}

export async function getShareBalances(params?: { fundId?: number; clientId?: number }) {
  return fetchJson<ShareBalance[]>(`/share/balances${buildQuery({ fund_id: params?.fundId, client_id: params?.clientId })}`);
}

export async function getFees() {
  return fetchJson<FeeRecord[]>('/fee');
}

export async function getImportBatches() {
  return fetchJson<ImportBatch[]>('/import');
}

export async function getImportBatch(batchId: number) {
  return fetchJson<ImportBatch>(`/import/${batchId}`);
}

export async function getFunds(page = 1, size = 50) {
  return fetchJson<ApiListResponse<Fund>>(`/fund${buildQuery({ page, size })}`);
}

export async function getClients(page = 1, size = 50) {
  return fetchJson<ApiListResponse<Client>>(`/client${buildQuery({ page, size })}`);
}

export async function getAccounts(params?: { page?: number; size?: number; fundId?: number; clientId?: number }) {
  return fetchJson<ApiListResponse<Account>>(`/account${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 50, fund_id: params?.fundId, client_id: params?.clientId })}`);
}

export async function getPositions(params?: { page?: number; size?: number; fundId?: number; accountId?: number; snapshotDate?: string }) {
  return fetchJson<ApiListResponse<Position>>(`/position${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 100, fund_id: params?.fundId, account_id: params?.accountId, snapshot_date: params?.snapshotDate })}`);
}

export async function getTransactions(params?: { page?: number; size?: number; fundId?: number; accountId?: number }) {
  return fetchJson<ApiListResponse<Transaction>>(`/transaction${buildQuery({ page: params?.page ?? 1, size: params?.size ?? 100, fund_id: params?.fundId, account_id: params?.accountId })}`);
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

export { API_BASE };
