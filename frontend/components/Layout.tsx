import Link from 'next/link';
import { ReactNode } from 'react';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { colors, styles } from '../lib/ui';

type LayoutProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  requiredPermission?: string;
};

type NavItem = {
  href: string;
  label: string;
  requiredPermission?: string;
};

export default function Layout({ title, children, subtitle, requiredPermission }: LayoutProps) {
  const { user, signOut, hasPermission } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const navItems: NavItem[] = [
    { href: '/', label: t('overview') },
    { href: '/dashboard', label: t('dashboard'), requiredPermission: 'dashboard.read' },
    { href: '/nav', label: t('nav'), requiredPermission: 'nav.read' },
    { href: '/shares', label: t('shares'), requiredPermission: 'shares.read' },
    { href: '/funds', label: t('funds'), requiredPermission: 'nav.read' },
    { href: '/accounts', label: t('accounts'), requiredPermission: 'accounts.read' },
    { href: '/clients', label: t('clients'), requiredPermission: 'clients.read' },
    { href: '/reports', label: t('reports'), requiredPermission: 'reports.read' },
    { href: `/customers/${user?.client_scope_id || 1}`,
      label: t('customerView'),
      requiredPermission: 'customer.read' },
    { href: '/import', label: t('import'), requiredPermission: 'import.read' },
  ];
  const visibleNavItems = navItems.filter((item) => !item.requiredPermission || hasPermission(item.requiredPermission));
  const showPermissionBanner = requiredPermission && !hasPermission(requiredPermission);

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
              {visibleNavItems.map((item) => (
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
        {showPermissionBanner ? (
          <div style={{ ...styles.card, marginBottom: 16, color: colors.warning }}>
            {t('permissionRequiredPage')}
          </div>
        ) : null}
        {children}
      </div>
    </div>
  );
}
