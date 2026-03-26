import { colors, formatNumber } from '../lib/ui';

type TrendData = {
  label: string;
  value: number;
};

export default function TrendChart({ data, valueFormat = 'number' }: { data: TrendData[], valueFormat?: 'number' | 'currency' }) {
  if (!data || !data.length) {
    return <p style={{ color: colors.muted, fontSize: 14 }}>No trend data available.</p>;
  }

  const values = data.map(d => d.value);
  const maxAbs = Math.max(...values.map(Math.abs), 1);

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {data.map((item, idx) => {
        const width = `${Math.max((Math.abs(item.value) / maxAbs) * 100, 4)}%`;
        const isPositive = item.value >= 0;
        
        return (
          <div key={item.label || idx}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6, color: colors.text }}>
              <span style={{ fontWeight: 500 }}>{item.label}</span>
              <strong>{valueFormat === 'currency' ? `$${formatNumber(item.value)}` : formatNumber(item.value, 6)}</strong>
            </div>
            <div style={{ background: '#f3f4f6', borderRadius: 4, overflow: 'hidden', height: 8 }}>
              <div
                style={{
                  width,
                  height: '100%',
                  borderRadius: 4,
                  background: isPositive ? colors.primary : colors.danger,
                  transition: 'width 0.3s ease'
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
