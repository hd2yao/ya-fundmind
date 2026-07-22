import { useEffect, useState } from "react";

import { getResource } from "../api/client";
import type { ApiResource } from "../api/types";

type ResourceState<T> = {
  loading: boolean;
  resource: ApiResource<T> | null;
  error: string | null;
};

export function useApiResource<T>(path: string): ResourceState<T> {
  const [state, setState] = useState<ResourceState<T>>({ loading: true, resource: null, error: null });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, resource: null, error: null });
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
  }, [path]);

  return state;
}
