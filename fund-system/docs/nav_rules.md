# NAV Rules (V1)

1. NAV snapshots are append-only and immutable once locked.
2. `nav_record.is_locked = true` means no edits are allowed.
3. NAV calculations should use price and FX snapshots from the same valuation date.
4. Any correction is applied as a new NAV snapshot, not an update of an old one.
