import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Legend } from "recharts";
import { api } from "../api";
import { Card, Spinner } from "../components/ui";
import type { MatrixCell } from "../types";

const SCORE: Record<MatrixCell["level"], number> = { full: 3, partial: 2, addon: 1, none: 0 };
const GLYPH: Record<MatrixCell["level"], string> = { full: "●", partial: "◐", addon: "◍", none: "○" };
const COLOR: Record<string, string> = {
  jfrog: "#41bf47", sonatype: "#79b62f", gitlab: "#fc6d26",
  github: "#8b5cf6", docker: "#2496ed", snyk: "#b45ab8",
};

export default function Compare() {
  const q = useQuery({ queryKey: ["matrix"], queryFn: api.matrix });
  const [selected, setSelected] = useState<string[]>(["jfrog", "sonatype", "gitlab"]);
  if (!q.data) return <Spinner />;
  const m = q.data;
  const toggle = (v: string) =>
    setSelected((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));
  const radarData = m.rows.map((r) => ({
    capability: r.capability.replace(" / ", "/"),
    ...Object.fromEntries(selected.map((v) => [v, SCORE[r.values[v].level]])),
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {m.vendors.map((v) => (
          <button key={v} onClick={() => v !== "jfrog" && toggle(v)}
                  className={`rounded-full border px-3 py-1 text-sm ${selected.includes(v)
                    ? "border-emerald-600 bg-emerald-900/40 text-emerald-200"
                    : "border-slate-700 text-slate-400"} ${v === "jfrog" ? "cursor-default font-bold" : ""}`}>
            {m.vendor_labels[v] ?? v}
          </button>
        ))}
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400">
                <th className="p-2">Capability</th>
                {selected.map((v) => <th key={v} className="p-2">{m.vendor_labels[v] ?? v}</th>)}
              </tr>
            </thead>
            <tbody>
              {m.rows.map((r) => (
                <tr key={r.capability} className="border-t border-slate-800">
                  <td className="p-2 font-medium text-slate-200">{r.capability}</td>
                  {selected.map((v) => {
                    const cell = r.values[v];
                    return (
                      <td key={v} className="p-2" title={cell.note}>
                        <span className={cell.level === "full" ? "text-emerald-300"
                          : cell.level === "partial" ? "text-amber-300"
                          : cell.level === "addon" ? "text-sky-300" : "text-slate-600"}>
                          {GLYPH[cell.level]} {cell.level}
                        </span>
                        {cell.note && <span className="ml-1 text-xs text-slate-500">({cell.note})</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-500">Curated matrix (config/feature_matrix.yaml) — facts are human-reviewed, not LLM-generated.</p>
      </Card>

      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-300">Capability radar</h3>
        <div className="h-96">
          <ResponsiveContainer>
            <RadarChart data={radarData} outerRadius="70%">
              <PolarGrid stroke="#334155" />
              <PolarAngleAxis dataKey="capability" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              {selected.map((v) => (
                <Radar key={v} name={m.vendor_labels[v] ?? v} dataKey={v}
                       stroke={COLOR[v] ?? "#ccc"} fill={COLOR[v] ?? "#ccc"} fillOpacity={0.15} />
              ))}
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
