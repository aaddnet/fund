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

type NavGroup = {
  label: string;
  items: NavItem[];
};

export default function Layout({ title, children, subtitle, requiredPermission }: LayoutProps) {
  const { user, signOut, hasPermission } = useAuth();
  const { locale, setLocale, t } = useI18n();

  const navGroups: NavGroup[] = [
    {
      label: t('navGroupOverview'),
      items: [
        { href: '/', label: t('overview') },
        { href: '/dashboard', label: t('dashboard'), requiredPermission: 'dashboard.read' },
      ],
    },
    {
      label: t('navGroupFund'),
      items: [
        { href: '/funds', label: t('funds'), requiredPermission: 'nav.read' },
        { href: '/nav', label: t('nav'), requiredPermission: 'nav.read' },
        { href: '/shares', label: t('shares'), requiredPermission: 'shares.read' },
        { href: '/register', label: t('register'), requiredPermission: 'shares.read' },
      ],
    },
    {
      label: t('navGroupAccount'),
      items: [
        { href: '/accounts', label: t('accounts'), requiredPermission: 'accounts.read' },
        { href: '/transactions', label: '交易管理', requiredPermission: 'accounts.read' },
        { href: '/import', label: t('import'), requiredPermission: 'import.read' },
        { href: '/pdf-import', label: 'PDF 年度账单', requiredPermission: 'import.read' },
        { href: '/cash', label: t('cash'), requiredPermission: 'nav.read' },
      ],
    },
    {
      label: t('navGroupClient'),
      items: [
        { href: '/clients', label: t('clients'), requiredPermission: 'clients.read' },
        { href: `/customers/${user?.client_scope_id || 1}`, label: t('customerView'), requiredPermission: 'customer.read' },
      ],
    },
    {
      label: t('navGroupOps'),
      items: [
        { href: '/reports', label: t('reports'), requiredPermission: 'reports.read' },
        { href: '/initialize', label: t('initialize'), requiredPermission: 'clients.write' },
        { href: '/settings', label: t('settings'), requiredPermission: 'nav.read' },
      ],
    },
  ];

  // Filter groups: keep only items the user can see, drop empty groups
  const visibleGroups = navGroups
    .map(group => ({
      ...group,
      items: group.items.filter(item => !item.requiredPermission || hasPermission(item.requiredPermission)),
    }))
    .filter(group => group.items.length > 0);

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
          </div>
          {/* Grouped navigation */}
          <nav style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 16, paddingTop: 16, borderTop: `1px solid ${colors.border}` }}>
            {visibleGroups.map(group => (
              <div key={group.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ fontSize: 11, color: colors.muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, marginRight: 4, whiteSpace: 'nowrap' }}>
                  {group.label}
                </span>
                {group.items.map(item => (
                  <Link
                    key={item.href}
                    href={item.href}
                    style={{
                      color: colors.text,
                      textDecoration: 'none',
                      padding: '6px 10px',
                      borderRadius: 8,
                      border: `1px solid ${colors.border}`,
                      background: '#fff',
                      fontWeight: 600,
                      fontSize: 13,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            ))}
          </nav>
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
