import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card, Spinner } from "../components/ui";

export default function Competitors() {
  const q = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  if (!q.data) return <Spinner />;
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {q.data.map((c) => (
        <Link key={c.slug} to={`/competitors/${c.slug}`}>
          <Card className="transition hover:border-emerald-700">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full" style={{ background: c.color }} />
              <span className="text-lg font-bold">{c.name}</span>
            </div>
            <div className="mt-2 flex gap-4 text-sm text-slate-400">
              <span>{c.article_count} items (14d)</span>
              <span className={c.high_impact_count ? "text-red-300" : ""}>{c.high_impact_count} high-impact</span>
            </div>
            <div className="mt-1 text-xs text-slate-500">
              last activity: {c.last_activity ? new Date(c.last_activity).toLocaleDateString() : "—"}
            </div>
          </Card>
        </Link>
      ))}
    </div>
  );
}
