import { NavLink, Outlet } from "react-router-dom";
import StatusStrip from "./components/StatusStrip";

const tabs = [
  { to: "/", label: "Today" },
  { to: "/feed", label: "Feed" },
  { to: "/competitors", label: "Competitors" },
  { to: "/compare", label: "Compare" },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <StatusStrip />
      <nav className="flex gap-1 border-b border-slate-800 bg-slate-900/60 px-4">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.to === "/"}
            className={({ isActive }) =>
              `px-4 py-2 text-sm font-medium ${isActive
                ? "border-b-2 border-emerald-400 text-emerald-300"
                : "text-slate-400 hover:text-slate-200"}`}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <main className="mx-auto max-w-6xl p-4"><Outlet /></main>
    </div>
  );
}
