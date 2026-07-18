"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/rfqs", label: "RFQ Inbox" },
  { href: "/rates", label: "Rate Requests" },
  { href: "/quotes", label: "Quotations" },
  { href: "/follow-ups", label: "Follow-ups" },
  { href: "/bookings", label: "Bookings" },
  { href: "/documents", label: "Documents" },
  { href: "/issues", label: "Issues" },
  { href: "/customers", label: "Customers" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-slate-200 bg-white">
      <div className="px-5 py-5">
        <div className="text-lg font-semibold text-slate-900">Freight AI Ops</div>
        <div className="text-xs text-slate-500">Sales &amp; Operations</div>
      </div>
      <nav className="px-3 pb-6">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-md px-3 py-2 text-sm font-medium ${
                active
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
