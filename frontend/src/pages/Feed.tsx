import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Card, ErrorBox, ImpactBadge, Spinner, Tag } from "../components/ui";
import type { Article } from "../types";

const DOMAINS = ["", "artifact_management", "container_registry", "devsecops_scanning", "cicd", "sbom_supply_chain", "other"];
const EVENTS = ["", "product_launch", "feature_update", "security_advisory", "pricing_change", "funding_ma", "partnership", "other"];
const COMPETITORS = ["", "sonatype", "gitlab", "github", "docker", "snyk"];

function DeltaPanel({ a }: { a: Article }) {
  if (!a.delta) return null;
  return (
    <div className="mt-2 rounded-lg border border-emerald-900 bg-emerald-950/40 p-2 text-xs">
      <div className="font-bold text-emerald-300">JFrog Delta — {a.delta.strategic_impact.toUpperCase()}</div>
      <div className="mt-1 text-slate-300"><b>Move:</b> {a.delta.move}</div>
      <div className="text-slate-300"><b>JFrog equivalent:</b> {a.delta.jfrog_equivalent}</div>
      {a.delta.talking_points.length > 0 && (
        <ul className="mt-1 list-inside list-disc text-slate-400">
          {a.delta.talking_points.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      )}
    </div>
  );
}

export default function Feed() {
  const [f, setF] = useState({ competitor: "", domain: "", event_type: "", min_impact: 0, q: "", page: 1 });
  const feed = useQuery({
    queryKey: ["articles", f],
    queryFn: () => api.articles({ ...f }),
    placeholderData: (prev) => prev,
  });
  const sel = "rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <select className={sel} value={f.competitor} onChange={(e) => setF({ ...f, competitor: e.target.value, page: 1 })}>
          {COMPETITORS.map((c) => <option key={c} value={c}>{c || "all competitors"}</option>)}
        </select>
        <select className={sel} value={f.domain} onChange={(e) => setF({ ...f, domain: e.target.value, page: 1 })}>
          {DOMAINS.map((d) => <option key={d} value={d}>{d || "all domains"}</option>)}
        </select>
        <select className={sel} value={f.event_type} onChange={(e) => setF({ ...f, event_type: e.target.value, page: 1 })}>
          {EVENTS.map((ev) => <option key={ev} value={ev}>{ev || "all events"}</option>)}
        </select>
        <select className={sel} value={f.min_impact} onChange={(e) => setF({ ...f, min_impact: +e.target.value, page: 1 })}>
          <option value={0}>any impact</option><option value={3}>impact ≥ 3</option><option value={4}>impact ≥ 4</option>
        </select>
        <input className={`${sel} flex-1`} placeholder="search…" value={f.q}
               onChange={(e) => setF({ ...f, q: e.target.value, page: 1 })} />
      </div>

      {feed.isLoading && <Spinner label="Loading feed…" />}
      {feed.isError && <ErrorBox error={feed.error} />}
      {feed.data && (
        <>
          <div className="text-xs text-slate-500">{feed.data.total} items</div>
          {feed.data.items.map((a) => (
            <Card key={a.id}>
              <div className="flex flex-wrap items-center gap-2">
                <ImpactBadge value={a.jfrog_impact} />
                {a.competitors.map((c) => <Tag key={c}>{c}</Tag>)}
                {a.domain && <Tag>{a.domain}</Tag>}
                {a.event_type && <Tag>{a.event_type}</Tag>}
                <span className="ml-auto text-xs text-slate-500">
                  {a.published_at ? new Date(a.published_at).toLocaleDateString() : ""} · {a.source_name}
                </span>
              </div>
              <a href={a.url} target="_blank" rel="noreferrer"
                 className="mt-1 block font-semibold text-slate-100 hover:text-emerald-300">{a.title}</a>
              {a.summary && <p className="mt-1 text-sm text-slate-300">{a.summary}</p>}
              {a.so_what && <p className="mt-1 text-sm italic text-amber-200/90">So what: {a.so_what}</p>}
              <DeltaPanel a={a} />
            </Card>
          ))}
          <div className="flex items-center gap-2 text-sm">
            <button disabled={f.page <= 1} onClick={() => setF({ ...f, page: f.page - 1 })}
                    className="rounded bg-slate-800 px-3 py-1 disabled:opacity-40">prev</button>
            <span>page {f.page}</span>
            <button disabled={f.page * feed.data.page_size >= feed.data.total}
                    onClick={() => setF({ ...f, page: f.page + 1 })}
                    className="rounded bg-slate-800 px-3 py-1 disabled:opacity-40">next</button>
          </div>
        </>
      )}
    </div>
  );
}
