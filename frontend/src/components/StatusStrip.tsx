import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

export default function StatusStrip() {
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, refetchInterval: 5000 });
  const refresh = useMutation({
    mutationFn: api.refresh,
    onSettled: () => qc.invalidateQueries(),
  });
  if (!meta.data) return null;
  const m = meta.data;
  const running = m.refresh_state.running;
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 bg-slate-900 px-4 py-2 text-xs text-slate-400">
      <span className="font-bold text-emerald-400">🐸 Ribbit</span>
      {m.demo_mode && (
        <span className="rounded bg-amber-500/20 px-2 py-0.5 font-semibold text-amber-300">
          DEMO MODE — bundled data, no live LLM
        </span>
      )}
      <span>LLM: {m.demo_mode ? "none" : `${m.provider}/${m.model}`}</span>
      <span>last refresh: {m.last_refresh ? new Date(m.last_refresh).toLocaleString() : "never"}</span>
      {running && <span className="text-sky-300">refreshing: {m.refresh_state.stage}…</span>}
      {m.refresh_state.errors.length > 0 && (
        <span className="text-red-400" title={m.refresh_state.errors.join("\n")}>
          {m.refresh_state.errors.length} source error(s)
        </span>
      )}
      <button
        onClick={() => refresh.mutate()}
        disabled={m.demo_mode || running}
        title={m.demo_mode ? "Disabled in demo mode" : "Fetch + analyze now"}
        className="ml-auto rounded-md bg-emerald-600 px-3 py-1 font-semibold text-white disabled:opacity-40">
        {running ? "Running…" : "Refresh now"}
      </button>
    </div>
  );
}
