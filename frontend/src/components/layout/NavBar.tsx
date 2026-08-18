import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Chat", end: true },
  { to: "/assets", label: "Catalog" },
  { to: "/lineage", label: "Lineage" },
  { to: "/glossary", label: "Glossary" },
];

export function NavBar() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-4">
        <span className="text-lg font-semibold tracking-tight text-slate-900">
          Context<span className="text-indigo-600">IQ</span>
        </span>
        <nav className="flex gap-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
