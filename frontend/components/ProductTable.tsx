import { ReactNode } from 'react';
import { styles } from '../lib/ui';

export type Column<T> = {
  key: string;
  title: string;
  render: (row: T) => ReactNode;
};

export default function ProductTable<T>({ columns, rows, emptyText }: { columns: Column<T>[]; rows: T[]; emptyText: string }) {
  if (rows.length === 0) {
    return <p style={{ color: '#64748b' }}>{emptyText}</p>;
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={styles.table}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} style={styles.th}>{column.title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column.key} style={styles.td}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
