"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Booking } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Panel } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

function Bookings() {
  const [items, setItems] = useState<Booking[]>([]);
  useEffect(() => {
    api.get<Booking[]>("/api/bookings").then(setItems).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Bookings / Job Files</h1>
        <p className="mt-1 text-sm text-slate-500">
          Won quotes converted into operational shipments. Convert a quote from
          its detail page.
        </p>
      </div>
      <Panel title="All bookings">
        {items.length === 0 ? (
          <p className="text-sm text-slate-500">
            No bookings yet — approve &amp; send a quote, then convert it once the
            customer confirms.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Job</th>
                <th>Route</th>
                <th>Value</th>
                <th>ETD / ETA</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="py-2">
                    <Link className="text-brand-600 hover:underline" href={`/bookings/${b.id}`}>
                      {b.job_number ?? `#${b.id}`}
                    </Link>
                  </td>
                  <td>{b.origin ?? "?"} → {b.destination ?? "?"}</td>
                  <td>{b.agreed_price != null ? `${b.agreed_price.toLocaleString()} ${b.currency}` : "—"}</td>
                  <td className="text-slate-500">{b.etd ?? "—"} / {b.eta ?? "—"}</td>
                  <td><StatusBadge value={b.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

export default function BookingsPage() {
  return (
    <RequireAuth>
      <Bookings />
    </RequireAuth>
  );
}
