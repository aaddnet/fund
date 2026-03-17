export const colors = {
  bg: '#f5f7fb',
  card: '#ffffff',
  text: '#0f172a',
  muted: '#64748b',
  border: '#e2e8f0',
  primary: '#2563eb',
  success: '#16a34a',
  warning: '#d97706',
  danger: '#dc2626',
  chipBg: '#eff6ff',
};

export const styles = {
  page: {
    minHeight: '100vh',
    background: colors.bg,
    color: colors.text,
  } as const,
  shell: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '24px',
  } as const,
  card: {
    background: colors.card,
    border: `1px solid ${colors.border}`,
    borderRadius: 16,
    padding: 20,
    boxShadow: '0 8px 24px rgba(15, 23, 42, 0.06)',
  } as const,
  grid3: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 16,
  } as const,
  grid2: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: 16,
  } as const,
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
  },
  th: {
    textAlign: 'left' as const,
    padding: '12px 10px',
    fontSize: 13,
    color: colors.muted,
    borderBottom: `1px solid ${colors.border}`,
  },
  td: {
    padding: '12px 10px',
    borderBottom: `1px solid ${colors.border}`,
    verticalAlign: 'top' as const,
  },
  input: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: 10,
    border: `1px solid ${colors.border}`,
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box' as const,
  },
  label: {
    display: 'block',
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 6,
    color: colors.muted,
  },
  buttonPrimary: {
    background: colors.primary,
    color: '#fff',
    border: 'none',
    padding: '10px 14px',
    borderRadius: 10,
    cursor: 'pointer',
    fontWeight: 600,
  } as const,
  buttonSecondary: {
    background: '#fff',
    color: colors.text,
    border: `1px solid ${colors.border}`,
    padding: '10px 14px',
    borderRadius: 10,
    cursor: 'pointer',
    fontWeight: 600,
  } as const,
  chip: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '4px 10px',
    borderRadius: 999,
    background: colors.chipBg,
    color: colors.primary,
    fontSize: 12,
    fontWeight: 700,
  } as const,
};

export function formatNumber(value: number | string, fractionDigits = 2) {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  }).format(Number(value));
}
