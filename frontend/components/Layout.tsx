import Link from 'next/link';
import { ReactNode } from 'react';

const navItems = [
  { href: '/', label: 'Home' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/nav', label: 'NAV' },
  { href: '/shares', label: 'Shares' },
  { href: '/accounts', label: 'Accounts' },
  { href: '/clients', label: 'Clients' },
  { href: '/import', label: 'Import' },
];

export default function Layout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main style={{ maxWidth: 960, margin: '0 auto', fontFamily: 'sans-serif', padding: '24px' }}>
      <nav style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
        {navItems.map((item) => (
          <Link key={item.href} href={item.href} style={{ color: '#0f62fe', textDecoration: 'none' }}>
            {item.label}
          </Link>
        ))}
      </nav>
      <h1>{title}</h1>
      <section>{children}</section>
    </main>
  );
}
