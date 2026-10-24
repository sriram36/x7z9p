const BASE = import.meta.env.VITE_API_BASE ?? "";

export async function get(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ""));
  const res = await fetch(`${BASE}${path}${qs.size ? `?${qs}` : ""}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

/** Small data-loading hook: re-fetches when `deps` change, ignores stale responses. */
import { useEffect, useState } from "react";
export function useApi(path, params, enabled = true) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const key = JSON.stringify([path, params, enabled]);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    get(path, params)
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error, loading: false }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
