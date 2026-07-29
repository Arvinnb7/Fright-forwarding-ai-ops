"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, API_BASE_URL, getToken } from "@/lib/api";
import { RFQ, RFQ_STATUSES } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, Panel, TextArea, ErrorText } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

const PAGE_SIZE = 25;

function Inbox() {
  const router = useRouter();
  const [raw, setRaw] = useState("");
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState("");
  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  // "Unassigned" is the one that matters commercially: it is where enquiries
  // the mailbox brought in overnight sit until somebody picks them up.
  const [scope, setScope] = useState<"team" | "mine" | "unassigned">("team");

  function load() {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (search) params.set("search", search);
    if (statusFilter) params.set("status_filter", statusFilter);
    if (scope === "mine") params.set("mine", "true");
    if (scope === "unassigned") params.set("unassigned", "true");
    fetch(`${API_BASE_URL}/api/rfqs?${params}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then(async (res) => {
        setTotal(Number(res.headers.get("X-Total-Count") ?? 0));
        setRfqs(await res.json());
      })
      .catch(() => {});
  }
  useEffect(load, [search, statusFilter, page, scope]);

  async function exportCsv() {
    const res = await fetch(`${API_BASE_URL}/api/exports/rfqs.csv`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rfqs.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function parse() {
    setError("");
    setParsing(true);
    try {
      const res = await api.post<{ rfq: RFQ }>("/api/rfqs/parse", {
        raw_message: raw,
        persist: true,
      });
      router.push(`/rfqs/${res.rfq.id}`);
    } catch (e) {
      setError((e as Error).message || "Failed to parse RFQ.");
    } finally {
      setParsing(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">RFQs</h1>
        <p className="mt-1 text-sm text-slate-500">
          Connected mailboxes create RFQs automatically. Use the box below for
          anything that arrives another way — WhatsApp, a phone call, a portal.
        </p>
      </div>

      <Panel
        title="New RFQ from text"
        actions={
          <Button onClick={parse} disabled={parsing || raw.trim().length === 0}>
            {parsing ? "Parsing…" : "Parse & create"}
          </Button>
        }
      >
        <TextArea value={raw} onChange={setRaw} rows={6} />
        <div className="mt-2">
          <ErrorText>{error}</ErrorText>
        </div>
      </Panel>

      <Panel
        title={`RFQs (${total})`}
        actions={
          <div className="flex flex-wrap gap-2">
            <div className="flex overflow-hidden rounded-md border border-slate-300">
              {(["team", "mine", "unassigned"] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => { setPage(0); setScope(option); }}
                  className={`px-3 py-1 text-sm ${
                    scope === option
                      ? "bg-brand-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {option === "team" ? "Team" : option === "mine" ? "My work" : "Unassigned"}
                </button>
              ))}
            </div>
            <input
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              placeholder="Search route/commodity…"
              value={search}
              onChange={(e) => { setPage(0); setSearch(e.target.value); }}
            />
            <select
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={statusFilter}
              onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }}
            >
              <option value="">All statuses</option>
              {RFQ_STATUSES.map((s) => (<option key={s}>{s}</option>))}
            </select>
            <Button variant="secondary" onClick={exportCsv}>CSV</Button>
          </div>
        }
      >
        {rfqs.length === 0 ? (
          <p className="text-sm text-slate-500">
            {scope === "unassigned"
              ? "Nothing waiting to be picked up."
              : scope === "mine"
                ? "Nothing assigned to you."
                : "No RFQs match."}
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Ref</th>
                <th>Route</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Missing</th>
              </tr>
            </thead>
            <tbody>
              {rfqs.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="py-2">
                    <Link className="text-brand-600 hover:underline" href={`/rfqs/${r.id}`}>
                      {r.reference ?? `#${r.id}`}
                    </Link>
                  </td>
                  <td>
                    {r.origin ?? "?"} → {r.destination ?? "?"}
                  </td>
                  <td>{r.transport_mode ?? "—"}</td>
                  <td>
                    <StatusBadge value={r.status} />
                  </td>
                  <td className="text-slate-500">{r.missing_fields.length}</td>
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

export default function RFQInboxPage() {
  return (
    <RequireAuth>
      <Inbox />
    </RequireAuth>
  );
}
