async function get(path) {
  const res = await fetch(`/api${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  meta: () => get("/meta"),
  decision: (date, cutoff) => get(`/decision/${date}?cutoff=${encodeURIComponent(cutoff)}`),
  accuracy: (cutoff) => get(`/accuracy?cutoff=${encodeURIComponent(cutoff)}`),
  horizon: () => get("/horizon"),
};
