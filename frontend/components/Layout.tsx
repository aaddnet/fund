import Link from 'next/link';
import { ReactNode } from 'react';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { colors, styles } from '../lib/ui';

export default function Layout({ title, children, subtitle }: { title: string; subtitle?: string; children: ReactNode }) {
  const { user, signOut } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const navItems = [
    { href: '/', label: t('overview') },
    { href: '/dashboard', label: t('dashboard') },
    { href: '/nav', label: t('nav') },
    { href: '/shares', label: t('shares') },
    { href: '/accounts', label: t('accounts') },
    { href: '/clients', label: t('clients') },
    { href: '/reports', label: t('reports') },
    { href: '/customers/1', label: t('customerView') },
    { href: '/import', label: t('import') },
  ];

  return (
    <div style={styles.page}>
      <div style={styles.shell}>
        <header style={{ ...styles.card, marginBottom: 20, padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 12, color: colors.primary, fontWeight: 800, letterSpacing: 1.2 }}>{t('appName').toUpperCase()}</div>
              <h1 style={{ margin: '8px 0 6px', fontSize: 32 }}>{title}</h1>
              {subtitle ? <p style={{ margin: 0, color: colors.muted }}>{subtitle}</p> : null}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <select aria-label={t('language')} style={{ ...styles.input, width: 120 }} value={locale} onChange={(event) => setLocale(event.target.value as 'en' | 'zh')}>
                <option value='en'>{t('english')}</option>
                <option value='zh'>{t('chinese')}</option>
              </select>
              {user ? <span style={{ color: colors.muted, fontSize: 14 }}>{t('welcome')}: {user.display_name || user.username}</span> : null}
              {user ? <button style={styles.buttonSecondary} onClick={() => signOut()}>{t('logout')}</button> : null}
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
