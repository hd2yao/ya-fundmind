import { useCallback, useEffect, useState } from "react";

import { getResource } from "../api/client";
import type { ApiResource } from "../api/types";

type ResourceState<T> = {
  loading: boolean;
  resource: ApiResource<T> | null;
  error: string | null;
};

type RefreshableResourceState<T> = ResourceState<T> & {
  refresh: () => void;
  refreshVersion: number;
};

export function useApiResource<T>(path: string): RefreshableResourceState<T> {
  const [state, setState] = useState<ResourceState<T>>({ loading: true, resource: null, error: null });
  const [refreshVersion, setRefreshVersion] = useState(0);
  const refresh = useCallback(() => setRefreshVersion((current) => current + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setState((current) => ({ loading: true, resource: current.resource, error: null }));
    getResource<T>(path, controller.signal)
      .then((resource) => setState({ loading: false, resource, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          loading: false,
          resource: null,
          error: error instanceof Error ? error.message : "Local API request failed."
        });
      });
    return () => controller.abort();
  }, [path, refreshVersion]);

  return { ...state, refresh, refreshVersion };
}
