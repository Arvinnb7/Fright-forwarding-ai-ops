"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DashboardMetrics } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { RequireAuth } from "@/components/RequireAuth";
import { Panel } from "@/components/ui";

function money(v: number) {
  return v.toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function Dashboard() {
  const [m, setM] = useState<DashboardMetrics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<DashboardMetrics>("/api/reports/dashboard")
      .then(setM)
      .catch(() => setError("Could not load metrics."));
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          A fast overview of your commercial and operational workload.
        </p>
      </div>

      {error && <p className="mb-4 text-sm text-rose-600">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Today's RFQs" value={m?.rfqs_received ?? "—"} hint="Received today" />
        <StatCard label="Quotes Sent" value={m?.quotes_sent ?? "—"} hint="Sent today" />
        <StatCard label="Pending Rates" value={m?.pending_rates ?? "—"} hint="Awaiting partners" />
        <StatCard label="Follow-ups Due" value={m?.follow_ups_due ?? "—"} hint="Need action" />
        <StatCard label="Confirmed Bookings" value={m?.confirmed_bookings ?? "—"} hint="Today" />
        <StatCard
          label="Estimated Pipeline"
          value={m ? money(m.estimated_pipeline) : "—"}
          hint="Active opportunities"
        />
        <StatCard
          label="Estimated Margin"
          value={m ? money(m.estimated_margin) : "—"}
          hint="Expected gross margin"
        />
        <StatCard label="Lost / Won today" value={m ? `${m.lost_today} / ${m.won_today}` : "—"} />
      </div>

      <div className="mt-8">
        <Panel title="High-value opportunities">
          {!m || m.high_value_opportunities.length === 0 ? (
            <p className="text-sm text-slate-500">No active high-value quotes.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="py-1">Quote</th>
                  <th>Value</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {m.high_value_opportunities.map((q, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="py-2">{q.quote_number ?? "—"}</td>
                    <td>{q.selling_price ? money(q.selling_price) : "—"}</td>
                    <td>{q.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <Dashboard />
    </RequireAuth>
  );
}
