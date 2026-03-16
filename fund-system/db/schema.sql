CREATE TABLE IF NOT EXISTS fund (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  base_currency VARCHAR(8) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client (
  id BIGSERIAL PRIMARY KEY,
  fund_id BIGINT NOT NULL REFERENCES fund(id),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS account (
  id BIGSERIAL PRIMARY KEY,
  fund_id BIGINT NOT NULL REFERENCES fund(id),
  broker TEXT NOT NULL,
  account_no TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS holding (
  id BIGSERIAL PRIMARY KEY,
  fund_id BIGINT NOT NULL REFERENCES fund(id),
  asset_code TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS position (
  id BIGSERIAL PRIMARY KEY,
  fund_id BIGINT NOT NULL REFERENCES fund(id),
  account_id BIGINT REFERENCES account(id),
  asset_code TEXT NOT NULL,
  quantity NUMERIC(28,10) NOT NULL,
  snapshot_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transaction (
  id BIGSERIAL PRIMARY KEY,
  fund_id BIGINT NOT NULL REFERENCES fund(id),
  account_id BIGINT REFERENCES account(id),
  trade_date DATE NOT NULL,
  asset_code TEXT,
  tx_type TEXT NOT NULL,
  quantity NUMERIC(28,10),
  price NUMERIC(28,10),
  currency VARCHAR(8),
  fee NUMERIC(28,10) DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS import_batch (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,
  file_name TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exchange_rate (
  id BIGSERIAL PRIMARY KEY,
  base_currency VARCHAR(8) NOT NULL,
  quote_currency VARCHAR(8) NOT NULL,
  rate NUMERIC(28,10) NOT NULL,
  snapshot_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (base_currency, quote_currency, snapshot_date)
);

CREATE TABLE IF NOT EXISTS asset_price (
  id BIGSERIAL PRIMARY KEY,
  asset_code TEXT NOT NULL,
  price NUMERIC(28,10) NOT NULL,
  currency VARCHAR(8) NOT NULL,
  snapshot_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (asset_code, snapshot_date)
);

CREATE TABLE IF NOT EXISTS nav_record (
  id BIGSERIAL PRIMARY KEY,
  fund_id BIGINT NOT NULL REFERENCES fund(id),
  nav_date DATE NOT NULL,
  nav_value NUMERIC(28,10) NOT NULL,
  is_locked BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (fund_id, nav_date)
);

CREATE TABLE IF NOT EXISTS asset_snapshot (
  id BIGSERIAL PRIMARY KEY,
  nav_record_id BIGINT NOT NULL REFERENCES nav_record(id),
  asset_code TEXT NOT NULL,
  quantity NUMERIC(28,10) NOT NULL,
  price NUMERIC(28,10) NOT NULL,
  value_base NUMERIC(28,10) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS share_transaction (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES client(id),
  tx_date DATE NOT NULL,
  tx_type TEXT NOT NULL,
  shares NUMERIC(28,10) NOT NULL,
  nav_per_share NUMERIC(28,10) NOT NULL,
  amount NUMERIC(28,10) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fee_record (
  id BIGSERIAL PRIMARY KEY,
  fund_id BIGINT NOT NULL REFERENCES fund(id),
  fee_date DATE NOT NULL,
  fee_type TEXT NOT NULL,
  amount NUMERIC(28,10) NOT NULL,
  currency VARCHAR(8) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_client_fund_id ON client(fund_id);
CREATE INDEX IF NOT EXISTS idx_account_fund_id ON account(fund_id);
CREATE INDEX IF NOT EXISTS idx_position_fund_date ON position(fund_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_transaction_fund_date ON transaction(fund_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_asset_snapshot_nav_record_id ON asset_snapshot(nav_record_id);
CREATE INDEX IF NOT EXISTS idx_share_transaction_client_date ON share_transaction(client_id, tx_date);
CREATE INDEX IF NOT EXISTS idx_fee_record_fund_date ON fee_record(fund_id, fee_date);
