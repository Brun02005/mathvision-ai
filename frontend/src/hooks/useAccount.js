import { useCallback, useEffect, useState } from 'react';
import { errorMessage, getMe } from '../services/api';

/** The signed-in user's account: { account, error, refresh }. account is null while loading. */
export default function useAccount() {
  const [state, setState] = useState({ account: null, error: null });

  const load = useCallback(
    () => getMe()
      .then((account) => setState({ account, error: null }))
      .catch((err) => setState({ account: null, error: errorMessage(err) })),
    [],
  );

  useEffect(() => { load(); }, [load]);

  return { ...state, refresh: load };
}
