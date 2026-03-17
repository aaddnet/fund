import Layout from '../components/Layout';
import { getPlaceholderResource } from '../lib/api';

type Props = {
  total: number;
  error?: string;
};

export default function Page({ total, error }: Props) {
  return (
    <Layout title='Accounts'>
      {error ? <p style={{ color: 'crimson' }}>Backend warning: {error}</p> : null}
      <p>Placeholder account endpoint is connected.</p>
      <p>Total accounts returned: {total}</p>
    </Layout>
  );
}

export async function getServerSideProps() {
  try {
    const data = await getPlaceholderResource('/account');
    return { props: { total: data.pagination?.total ?? data.items?.length ?? 0 } };
  } catch (error) {
    return {
      props: {
        total: 0,
        error: error instanceof Error ? error.message : 'unknown error',
      },
    };
  }
}
