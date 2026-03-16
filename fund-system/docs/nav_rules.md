Base currency: USD

NAV formula:

asset_value = quantity * price
usd_value = asset_value * fx

total_asset = sum usd_value

nav = total_asset / total_shares

Snapshot rules:

- monthly snapshot
- snapshot immutable
- fx snapshot must match nav date
- price snapshot must match nav date

Share rules:

- subscription quarterly
- redemption quarterly
- shares = amount / nav

Fee rules:

yearly
>15%
30%
deduct from nav

No management fee
No FX split
