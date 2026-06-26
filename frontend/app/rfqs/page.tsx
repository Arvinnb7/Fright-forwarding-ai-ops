"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { RFQ } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, Panel, TextArea, ErrorText } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

function Inbox() {
  const router = useRouter();
  const [raw, setRaw] = useState("");
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState("");
  const [rfqs, setRfqs] = useState<RFQ[]>([]);

  function load() {
    api.get<RFQ[]>("/api/rfqs").then(setRfqs).catch(() => {});
  }
  useEffect(load, []);

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
        <h1 className="text-2xl font-semibold text-slate-900">RFQ Inbox</h1>
        <p className="mt-1 text-sm text-slate-500">
          Paste a customer email or message — the AI extracts structured shipment
          details and flags missing information.
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

      <Panel title="Recent RFQs">
        {rfqs.length === 0 ? (
          <p className="text-sm text-slate-500">No RFQs yet.</p>
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
