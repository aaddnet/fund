CREATE TABLE fund (
    id SERIAL PRIMARY KEY,
    name TEXT,
    base_currency TEXT,
    total_shares NUMERIC,
    current_nav NUMERIC,
    created_at TIMESTAMP
);

CREATE TABLE client (
    id SERIAL PRIMARY KEY,
    name TEXT,
    email TEXT,
    created_at TIMESTAMP
);

CREATE TABLE account (
    id SERIAL PRIMARY KEY,
    fund_id INT,
    platform TEXT,
    currency TEXT
);

CREATE TABLE position (
    id SERIAL PRIMARY KEY,
    account_id INT,
    asset_code TEXT,
    quantity NUMERIC,
    price NUMERIC,
    currency TEXT
);

CREATE TABLE exchange_rate (
    id SERIAL PRIMARY KEY,
    from_currency TEXT,
    to_currency TEXT,
    rate NUMERIC,
    snapshot_date DATE
);

CREATE TABLE asset_price (
    id SERIAL PRIMARY KEY,
    asset_code TEXT,
    price_usd NUMERIC,
    snapshot_date DATE
);

CREATE TABLE nav_record (
    id SERIAL PRIMARY KEY,
    fund_id INT,
    snapshot_date DATE,
    total_asset NUMERIC,
    total_shares NUMERIC,
    nav NUMERIC,
    is_locked BOOLEAN
);

CREATE TABLE asset_snapshot (
    id SERIAL PRIMARY KEY,
    nav_id INT,
    asset_code TEXT,
    value_usd NUMERIC
);

CREATE TABLE share_tx (
    id SERIAL PRIMARY KEY,
    client_id INT,
    fund_id INT,
    type TEXT,
    amount NUMERIC,
    shares NUMERIC,
    nav NUMERIC,
    tx_date DATE
);

CREATE TABLE fee_record (
    id SERIAL PRIMARY KEY,
    fund_id INT,
    year INT,
    fee NUMERIC
);
