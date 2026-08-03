import type { ArticleRef } from "../types";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-4 ${className}`}>{children}</div>;
}

export function ImpactBadge({ value }: { value: number | null }) {
  const v = value ?? 1;
  const color = v >= 4 ? "bg-red-500/20 text-red-300 border-red-500/40"
    : v === 3 ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
    : "bg-slate-600/20 text-slate-300 border-slate-600/40";
  return <span className={`rounded-md border px-1.5 py-0.5 text-xs font-semibold ${color}`}>impact {v}</span>;
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="rounded-md bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300">{children}</span>;
}

export function CitationChips({ ids, articles }: { ids: number[]; articles: Record<string, ArticleRef> }) {
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
      {ids.map((id) => {
        const ref = articles[String(id)];
        if (!ref) return null;
        const date = ref.published_at ? new Date(ref.published_at).toISOString().slice(0, 10) : "";
        return (
          <a key={id} href={ref.url} target="_blank" rel="noreferrer" title={`${ref.title} — ${ref.source_name}`}
             className="rounded bg-emerald-900/50 px-1 text-xs text-emerald-300 hover:bg-emerald-800">
            [{id}]{date && ` ${date}`}
          </a>
        );
      })}
    </span>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div className="p-8 text-center text-sm text-slate-400">{label}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  return <div className="rounded-lg border border-red-800 bg-red-950/40 p-3 text-sm text-red-300">
    {String(error)}
  </div>;
}
