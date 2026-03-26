import { ReactNode } from 'react';
import { colors, styles } from '../lib/ui';

export default function StatCard({ label, value, tone = 'default', hint }: { label: string; value: ReactNode; tone?: 'default' | 'success' | 'warning'; hint?: string }) {
  const toneColor = tone === 'success' ? colors.success : tone === 'warning' ? colors.warning : colors.primary;

  return (
    <div style={styles.card}>
      <div style={{ fontSize: 13, color: colors.muted, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: toneColor }}>{value}</div>
      {hint ? <div style={{ fontSize: 13, color: colors.muted, marginTop: 8 }}>{hint}</div> : null}
    </div>
  );
}
