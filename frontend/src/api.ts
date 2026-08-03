async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}
export const api = {
  meta: () => get<import("./types").Meta>("/api/meta"),
  digest: (date?: string) =>
    get<import("./types").Digest>(`/api/digest${date ? `?date=${date}` : ""}`),
  digestDates: () => get<string[]>("/api/digest/dates"),
  articles: (params: Record<string, string | number>) =>
    get<import("./types").ArticlePage>(`/api/articles?${new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== 0)
        .map(([k, v]) => [k, String(v)])))}`),
  competitors: () => get<import("./types").Competitor[]>("/api/competitors"),
  battlecard: (slug: string) => get<import("./types").Battlecard>(`/api/competitors/${slug}/battlecard`),
  matrix: () => get<import("./types").Matrix>("/api/matrix"),
  sources: () => get<import("./types").SourceHealth[]>("/api/sources/health"),
  refresh: () => fetch("/api/refresh", { method: "POST" }),
};
