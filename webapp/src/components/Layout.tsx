import { NavLink, Outlet } from "react-router-dom";
import { Home as HomeIcon, List, Wallet, Target, Repeat } from "lucide-react";

const tabs = [
  { to: "/", label: "Home", icon: HomeIcon, end: true },
  { to: "/transactions", label: "Tx", icon: List, end: false },
  { to: "/budgets", label: "Budgets", icon: Wallet, end: false },
  { to: "/goals", label: "Goals", icon: Target, end: false },
  { to: "/recurring", label: "Recur", icon: Repeat, end: false },
];

export default function Layout() {
  return (
    <div className="min-h-full pb-16">
      <main className="max-w-2xl mx-auto">
        <Outlet />
      </main>
      <nav className="fixed bottom-0 inset-x-0 bg-background/95 backdrop-blur border-t border-border h-14 flex items-end justify-around pb-2 text-[10px] font-medium">
        {tabs.map(t => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              "relative h-full flex flex-col items-center justify-end gap-1 " +
              (isActive ? "text-foreground after:content-[''] after:absolute after:bottom-0 after:left-1/2 after:-translate-x-1/2 after:w-[18px] after:h-[2px] after:bg-foreground"
                : "text-neutral-400")
            }
          >
            <t.icon size={18} strokeWidth={1.75} />
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
