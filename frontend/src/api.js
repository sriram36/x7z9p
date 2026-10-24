const BASE = import.meta.env.VITE_API_BASE ?? "";

export async function get(path, params = {}, retries = 2) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ""));
  const url = `${BASE}${path}${qs.size ? `?${qs}` : ""}`;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        let detail = res.statusText || `HTTP ${res.status}`;
        try {
          const body = await res.json();
          detail = body.detail ?? detail;
        } catch {
          /* body was not JSON */
        }
        if ([502, 503, 504].includes(res.status) && attempt < retries) {
          await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
          continue;
        }
        throw new Error(typeof detail === "string" && detail.trim() ? detail : `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      if (attempt < retries && !(err.message && err.message.startsWith("HTTP 4"))) {
        await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
        continue;
      }
      throw err;
    }
  }
}

/** Small data-loading hook: re-fetches when `deps` change, ignores stale responses. */
import { useEffect, useState } from "react";
export function useApi(path, params, enabled = true) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const [retryKey, setRetryKey] = useState(0);
  const key = JSON.stringify([path, params, enabled, retryKey]);

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

  const reload = () => setRetryKey((k) => k + 1);
  return { ...state, reload };
}

