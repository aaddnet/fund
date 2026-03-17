import Link from 'next/link';
import { ReactNode } from 'react';
import { colors, styles } from '../lib/ui';

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/nav', label: 'NAV' },
  { href: '/shares', label: 'Shares' },
  { href: '/accounts', label: 'Accounts' },
  { href: '/clients', label: 'Clients' },
  { href: '/import', label: 'Import' },
];

export default function Layout({ title, children, subtitle }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div style={styles.page}>
      <div style={styles.shell}>
        <header style={{ ...styles.card, marginBottom: 20, padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 12, color: colors.primary, fontWeight: 800, letterSpacing: 1.2 }}>FUND OPS CONSOLE</div>
              <h1 style={{ margin: '8px 0 6px', fontSize: 32 }}>{title}</h1>
              {subtitle ? <p style={{ margin: 0, color: colors.muted }}>{subtitle}</p> : null}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  style={{
                    color: colors.text,
                    textDecoration: 'none',
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: `1px solid ${colors.border}`,
                    background: '#fff',
                    fontWeight: 600,
                    fontSize: 14,
                  }}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
