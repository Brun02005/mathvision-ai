import { useCallback, useEffect, useState } from 'react';
import { healthCheck } from '../services/api';

/** Backend status: { online: null (checking) | true | false, info, refresh } */
export default function useHealth() {
  const [state, setState] = useState({ online: null, info: null });

  const check = useCallback(
    () => healthCheck()
      .then((info) => setState({ online: true, info }))
      .catch(() => setState({ online: false, info: null })),
    [],
  );

  useEffect(() => { check(); }, [check]);

  const refresh = useCallback(() => {
    setState({ online: null, info: null });
    return check();
  }, [check]);

  return { ...state, refresh };
}
