CREATE TABLE IF NOT EXISTS fund (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    base_currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    total_shares NUMERIC(20,6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS account (
    id SERIAL PRIMARY KEY,
    fund_id INT NOT NULL REFERENCES fund(id),
    client_id INT REFERENCES client(id),
    broker VARCHAR(100) NOT NULL,
    account_no VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS holding (
    id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES account(id),
    asset_code VARCHAR(50) NOT NULL,
    quantity NUMERIC(24,8) NOT NULL,
    as_of_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS position (
    id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES account(id),
    asset_code VARCHAR(50) NOT NULL,
    quantity NUMERIC(24,8) NOT NULL,
    average_cost NUMERIC(24,8),
    currency VARCHAR(10) NOT NULL,
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transaction (
    id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES account(id),
    trade_date DATE NOT NULL,
    asset_code VARCHAR(50) NOT NULL,
    quantity NUMERIC(24,8) NOT NULL,
    price NUMERIC(24,8) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    tx_type VARCHAR(50) NOT NULL,
    fee NUMERIC(24,8) NOT NULL DEFAULT 0,
    import_batch_id INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS import_batch (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    filename VARCHAR(255),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exchange_rate (
    id SERIAL PRIMARY KEY,
    base_currency VARCHAR(10) NOT NULL,
    quote_currency VARCHAR(10) NOT NULL,
    rate NUMERIC(20,8) NOT NULL,
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (base_currency, quote_currency, snapshot_date)
);

CREATE TABLE IF NOT EXISTS asset_price (
    id SERIAL PRIMARY KEY,
    asset_code VARCHAR(50) NOT NULL,
    price_usd NUMERIC(24,8) NOT NULL,
    source VARCHAR(20) NOT NULL,
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (asset_code, snapshot_date)
);

CREATE TABLE IF NOT EXISTS nav_record (
    id SERIAL PRIMARY KEY,
    fund_id INT NOT NULL REFERENCES fund(id),
    nav_date DATE NOT NULL,
    total_assets_usd NUMERIC(24,8) NOT NULL,
    total_shares NUMERIC(24,8) NOT NULL,
    nav_per_share NUMERIC(24,8) NOT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (fund_id, nav_date)
);

CREATE TABLE IF NOT EXISTS asset_snapshot (
    id SERIAL PRIMARY KEY,
    nav_record_id INT NOT NULL REFERENCES nav_record(id),
    asset_code VARCHAR(50) NOT NULL,
    quantity NUMERIC(24,8) NOT NULL,
    price_usd NUMERIC(24,8) NOT NULL,
    value_usd NUMERIC(24,8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS share_transaction (
    id SERIAL PRIMARY KEY,
    fund_id INT NOT NULL REFERENCES fund(id),
    client_id INT NOT NULL REFERENCES client(id),
    tx_date DATE NOT NULL,
    tx_type VARCHAR(20) NOT NULL,
    amount_usd NUMERIC(24,8) NOT NULL,
    shares NUMERIC(24,8) NOT NULL,
    nav_at_date NUMERIC(24,8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fee_record (
    id SERIAL PRIMARY KEY,
    fund_id INT NOT NULL REFERENCES fund(id),
    fee_date DATE NOT NULL,
    gross_return NUMERIC(12,6) NOT NULL,
    fee_rate NUMERIC(12,6) NOT NULL,
    fee_amount_usd NUMERIC(24,8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE transaction
    ADD CONSTRAINT fk_transaction_import_batch
    FOREIGN KEY (import_batch_id) REFERENCES import_batch(id);

CREATE INDEX IF NOT EXISTS idx_account_fund_id ON account(fund_id);
CREATE INDEX IF NOT EXISTS idx_position_snapshot_date ON position(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_transaction_trade_date ON transaction(trade_date);
CREATE INDEX IF NOT EXISTS idx_exchange_rate_snapshot_date ON exchange_rate(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_asset_price_snapshot_date ON asset_price(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_nav_record_date ON nav_record(nav_date);
CREATE INDEX IF NOT EXISTS idx_share_transaction_date ON share_transaction(tx_date);
