import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Card, CitationChips, ErrorBox, Spinner } from "../components/ui";

function CuratedList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <Card>
      <h3 className={`mb-2 text-sm font-bold ${tone}`}>{title}
        <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-normal text-slate-400">CURATED</span>
      </h3>
      <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
        {items.map((s, i) => <li key={i}>{s}</li>)}
      </ul>
    </Card>
  );
}

export default function CompetitorDetail() {
  const { slug = "" } = useParams();
  const q = useQuery({ queryKey: ["battlecard", slug], queryFn: () => api.battlecard(slug), retry: false });
  if (q.isLoading) return <Spinner />;
  if (q.isError) return <ErrorBox error={q.error} />;
  const b = q.data!;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="h-4 w-4 rounded-full" style={{ background: b.color }} />
        <h1 className="text-xl font-bold">{b.name} battlecard</h1>
        <Link to="/competitors" className="ml-auto text-sm text-slate-400 hover:text-slate-200">← all competitors</Link>
      </div>

      <Card className="border-emerald-900">
        <h3 className="mb-2 text-sm font-bold text-emerald-300">Recent moves & signals
          <span className="ml-2 rounded bg-emerald-900/60 px-1.5 py-0.5 text-[10px] font-normal text-emerald-300">
            GENERATED · CITED
          </span>
        </h3>
        {b.recent_moves.length === 0 && <p className="text-sm text-slate-500">No recent enriched items yet — run a refresh.</p>}
        <ul className="space-y-2 text-sm text-slate-200">
          {b.recent_moves.map((m, i) => (
            <li key={i}>• {m.text}<CitationChips ids={m.article_ids} articles={b.articles} /></li>
          ))}
        </ul>
        {b.generated_at && <p className="mt-2 text-xs text-slate-500">updated {new Date(b.generated_at).toLocaleString()}</p>}
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <CuratedList title="Strengths" items={b.base.strengths} tone="text-sky-300" />
        <CuratedList title="Weaknesses" items={b.base.weaknesses} tone="text-amber-300" />
        <CuratedList title="How JFrog wins" items={b.base.how_jfrog_wins} tone="text-emerald-300" />
      </div>
    </div>
  );
}
