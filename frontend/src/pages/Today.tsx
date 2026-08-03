import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Card, CitationChips, ErrorBox, Spinner } from "../components/ui";

export default function Today() {
  const [date, setDate] = useState<string>("");
  const dates = useQuery({ queryKey: ["digestDates"], queryFn: api.digestDates });
  const digest = useQuery({
    queryKey: ["digest", date],
    queryFn: () => api.digest(date || undefined),
    retry: false,
  });

  if (digest.isLoading) return <Spinner label="Loading digest…" />;
  if (digest.isError) return <ErrorBox error="No digest yet — run a refresh (or check demo mode)." />;
  const d = digest.data!;
  const s = d.sections;
  const kpis = [
    { label: "Top developments", value: s.top_developments.length },
    { label: "Competitors active", value: s.by_competitor.length },
    { label: "Threats", value: s.threats_opportunities.filter(t => t.kind === "threat").length },
    { label: "Opportunities", value: s.threats_opportunities.filter(t => t.kind === "opportunity").length },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Daily digest — {d.date}</h1>
        <select value={date} onChange={(e) => setDate(e.target.value)}
                className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm">
          <option value="">latest</option>
          {(dates.data ?? []).map((dt) => <option key={dt} value={dt}>{dt}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.label} className="text-center">
            <div className="text-2xl font-bold text-emerald-300">{k.value}</div>
            <div className="text-xs text-slate-400">{k.label}</div>
          </Card>
        ))}
      </div>

      <Card>
        <h2 className="mb-1 text-sm font-semibold text-slate-300">
          Executive summary
          <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-normal text-slate-400"
                title="Synthesis of the cited claims below. Unlike those claims, this paragraph carries no per-source citations.">
            AI SYNTHESIS
          </span>
        </h2>
        <p className="text-slate-100">{d.exec_summary}</p>
        <p className="mt-2 text-xs text-slate-500">generated {new Date(d.generated_at).toLocaleString()} · {d.model_used}</p>
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-semibold text-slate-300">Top developments</h2>
        <ul className="space-y-2">
          {s.top_developments.map((c, i) => (
            <li key={i} className="text-sm">• {c.text}<CitationChips ids={c.article_ids} articles={d.articles} /></li>
          ))}
          {s.top_developments.length === 0 && <li className="text-sm text-slate-500">Quiet day.</li>}
        </ul>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-slate-300">By competitor</h2>
          {s.by_competitor.map((b) => (
            <div key={b.competitor} className="mb-2">
              <div className="text-sm font-semibold capitalize text-slate-200">{b.competitor}</div>
              <ul>{b.highlights.map((h, i) => (
                <li key={i} className="text-sm text-slate-300">– {h.text}
                  <CitationChips ids={h.article_ids} articles={d.articles} /></li>))}
              </ul>
            </div>
          ))}
        </Card>
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-slate-300">Threats & opportunities</h2>
          <ul className="space-y-2">
            {s.threats_opportunities.map((t, i) => (
              <li key={i} className="text-sm">
                <span className={`mr-1 rounded px-1.5 py-0.5 text-xs font-bold ${
                  t.kind === "threat" ? "bg-red-500/20 text-red-300" : "bg-emerald-500/20 text-emerald-300"}`}>
                  {t.kind}
                </span>
                {t.text}<CitationChips ids={t.article_ids} articles={d.articles} />
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
