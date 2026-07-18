"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE_URL, getToken } from "@/lib/api";
import { Quote, QUOTE_STATUSES } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, Panel } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

const PAGE_SIZE = 25;

function money(v: number | null, c: string) {
  return v == null ? "—" : `${v.toLocaleString()} ${c}`;
}

function Quotes() {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);

  function load() {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (statusFilter) params.set("status_filter", statusFilter);
    fetch(`${API_BASE_URL}/api/quotes?${params}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then(async (res) => {
        setTotal(Number(res.headers.get("X-Total-Count") ?? 0));
        setQuotes(await res.json());
      })
      .catch(() => {});
  }
  useEffect(load, [statusFilter, page]);

  async function exportCsv() {
    const res = await fetch(`${API_BASE_URL}/api/exports/quotes.csv`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "quotes.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Quotations</h1>
      <Panel
        title={`Quotes (${total})`}
        actions={
          <div className="flex gap-2">
            <select
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={statusFilter}
              onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }}
            >
              <option value="">All statuses</option>
              {QUOTE_STATUSES.map((s) => (<option key={s}>{s}</option>))}
            </select>
            <Button variant="secondary" onClick={exportCsv}>CSV</Button>
          </div>
        }
      >
        {quotes.length === 0 ? (
          <p className="text-sm text-slate-500">No quotes match. Start one from an RFQ.</p>
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
                  <td><StatusBadge value={q.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {total > PAGE_SIZE && (
          <div className="mt-3 flex items-center justify-between text-sm">
            <Button variant="secondary" onClick={() => setPage(page - 1)} disabled={page === 0}>
              ← Prev
            </Button>
            <span className="text-slate-500">
              Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}
            </span>
            <Button
              variant="secondary"
              onClick={() => setPage(page + 1)}
              disabled={(page + 1) * PAGE_SIZE >= total}
            >
              Next →
            </Button>
          </div>
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
