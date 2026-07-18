"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Booking, ShipmentDocument } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Panel } from "@/components/ui";

interface Row {
  booking: Booking;
  docs: ShipmentDocument[];
}

function DocumentsOverview() {
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    (async () => {
      const bookings = await api.get<Booking[]>("/api/bookings?limit=25").catch(() => []);
      const withDocs = await Promise.all(
        bookings.map(async (booking) => ({
          booking,
          docs: await api
            .get<ShipmentDocument[]>(`/api/bookings/${booking.id}/documents`)
            .catch(() => []),
        }))
      );
      setRows(withDocs);
    })();
  }, []);

  const count = (docs: ShipmentDocument[], status: string) =>
    docs.filter((d) => d.status === status).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
        <p className="mt-1 text-sm text-slate-500">
          Document completion per shipment. Manage the checklist inside each job file.
        </p>
      </div>
      <Panel title="Shipments">
        {rows.length === 0 ? (
          <p className="text-sm text-slate-500">No bookings yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Job</th>
                <th>Route</th>
                <th>Tracked</th>
                <th>Received</th>
                <th>Outstanding</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ booking, docs }) => {
                const received = count(docs, "Received");
                const outstanding = docs.length - received;
                return (
                  <tr key={booking.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="py-2">
                      <Link className="text-brand-600 hover:underline" href={`/bookings/${booking.id}`}>
                        {booking.job_number ?? `#${booking.id}`}
                      </Link>
                    </td>
                    <td>{booking.origin ?? "?"} → {booking.destination ?? "?"}</td>
                    <td>{docs.length}</td>
                    <td className="text-green-700">{received}</td>
                    <td className={outstanding > 0 ? "font-medium text-rose-700" : "text-slate-500"}>
                      {outstanding}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <RequireAuth>
      <DocumentsOverview />
    </RequireAuth>
  );
}
