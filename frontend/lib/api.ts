const API_BASE = process.env.NEXT_PUBLIC_API || 'http://127.0.0.1:8000';

type ApiListResponse<T> = {
  items?: T[];
  pagination?: {
    page: number;
    size: number;
    total: number;
  };
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

export type FeeRecord = {
  id: number;
  fund_id: number;
  fee_date: string;
  gross_return: number;
  fee_rate: number;
  fee_amount_usd: number;
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
    const message = await response.text();
    throw new Error(message || `API ${path} failed with ${response.status}`);
  }
  return response.json();
}

export async function getHealth() {
  return fetchJson<{ status: string }>('/health');
}

export async function getHealthDb() {
  return fetchJson<{ db: string }>('/health/db');
}

export async function getNav() {
  return fetchJson<NavRecord[]>('/nav');
}

export async function getShareHistory() {
  return fetchJson<ShareTransaction[]>('/share/history');
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

export async function getPlaceholderResource(path: string) {
  return fetchJson<ApiListResponse<Record<string, unknown>>>(path);
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

export { API_BASE };
