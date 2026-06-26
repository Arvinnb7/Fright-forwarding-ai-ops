"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Quote } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Panel } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

function money(v: number | null, c: string) {
  return v == null ? "—" : `${v.toLocaleString()} ${c}`;
}

function Quotes() {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  useEffect(() => {
    api.get<Quote[]>("/api/quotes").then(setQuotes).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Quotations</h1>
      <Panel title="All quotes">
        {quotes.length === 0 ? (
          <p className="text-sm text-slate-500">No quotes yet. Start one from an RFQ.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Number</th>
                <th>Price</th>
                <th>Margin</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {quotes.map((q) => (
                <tr key={q.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="py-2">
                    <Link className="text-brand-600 hover:underline" href={`/quotes/${q.id}`}>
                      {q.quote_number ?? `#${q.id}`}
                    </Link>
                  </td>
                  <td>{money(q.selling_price, q.currency)}</td>
                  <td>
                    {q.gross_margin == null
                      ? "—"
                      : `${q.gross_margin} (${q.gross_margin_percentage ?? "—"}%)`}
                  </td>
                  <td>
                    <StatusBadge value={q.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

export default function QuotesPage() {
  return (
    <RequireAuth>
      <Quotes />
    </RequireAuth>
  );
}
