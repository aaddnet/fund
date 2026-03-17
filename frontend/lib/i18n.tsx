import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { getServerLocale, Locale, persistLocaleCookie } from './api';

const messages = {
  en: {
    appName: 'Fund Ops Console',
    overview: 'Overview',
    dashboard: 'Dashboard',
    nav: 'NAV',
    shares: 'Shares',
    accounts: 'Accounts',
    clients: 'Clients',
    reports: 'Reports',
    customerView: 'Customer View',
    import: 'Import',
    login: 'Login',
    logout: 'Logout',
    loggingIn: 'Signing in...',
    username: 'Username',
    password: 'Password',
    language: 'Language',
    english: 'English',
    chinese: '中文',
    loginTitle: 'Sign in to Fund Ops Console',
    loginSubtitle: 'Use your account to access operational dashboards and customer views.',
    authRequired: 'Please sign in to continue.',
    sessionExpired: 'Your session expired. Please sign in again.',
    welcome: 'Welcome',
  },
  zh: {
    appName: '基金运营控制台',
    overview: '总览',
    dashboard: '仪表盘',
    nav: '净值',
    shares: '份额',
    accounts: '账户',
    clients: '客户',
    reports: '报表',
    customerView: '客户视图',
    import: '导入',
    login: '登录',
    logout: '退出登录',
    loggingIn: '登录中...',
    username: '用户名',
    password: '密码',
    language: '语言',
    english: 'English',
    chinese: '中文',
    loginTitle: '登录基金运营控制台',
    loginSubtitle: '使用账号访问运营仪表盘与客户视图。',
    authRequired: '请先登录后继续。',
    sessionExpired: '登录已过期，请重新登录。',
    welcome: '欢迎',
  },
} as const;

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: keyof typeof messages.en) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children, initialLocale }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale || 'en');

  useEffect(() => {
    persistLocaleCookie(locale);
  }, [locale]);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      setLocale: (next) => setLocaleState(next),
      t: (key) => messages[locale][key],
    }),
    [locale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const value = useContext(I18nContext);
  if (!value) throw new Error('useI18n must be used within I18nProvider');
  return value;
}

export { getServerLocale };
