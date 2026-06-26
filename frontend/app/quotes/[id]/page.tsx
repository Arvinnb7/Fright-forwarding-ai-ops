"use client";

import { useEffect, useState } from "react";
import { api, API_BASE_URL, getToken } from "@/lib/api";
import { Quote } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, CopyButton, ErrorText, Panel, TextArea } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

const PENDING = "Pending approval";

function QuoteDetail({ id }: { id: number }) {
  const [quote, setQuote] = useState<Quote | null>(null);
  const [price, setPrice] = useState("");
  const [text, setText] = useState("");
  const [markSent, setMarkSent] = useState(true);
  const [lostReason, setLostReason] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  function load() {
    api.get<Quote>(`/api/quotes/${id}`).then((q) => {
      setQuote(q);
      setPrice(q.selling_price?.toString() ?? "");
      setText(q.quote_text ?? "");
    });
  }
  useEffect(load, [id]);

  async function decide(approved: boolean) {
    setBusy(approved ? "approve" : "reject");
    setError("");
    try {
      await api.post(`/api/quotes/${id}/approve`, {
        approved,
        selling_price: approved && price ? Number(price) : null,
        quote_text: approved ? text : null,
        mark_sent: approved && markSent,
        lost_reason: !approved ? lostReason : null,
      });
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function downloadPdf() {
    const res = await fetch(`${API_BASE_URL}/api/quotes/${id}/pdf`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${quote?.quote_number ?? "quote"}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!quote) return <p className="text-sm text-slate-500">Loading…</p>;
  const pending = quote.status === PENDING;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">
          {quote.quote_number ?? `Quote #${quote.id}`}
        </h1>
        <StatusBadge value={quote.status} />
      </div>

      <ErrorText>{error}</ErrorText>

      <Panel title="Pricing">
        <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <div className="text-xs uppercase text-slate-500">Cost</div>
            <div className="font-medium">
              {quote.cost_amount ?? "—"} {quote.currency}
            </div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-500">Selling price</div>
            {pending ? (
              <input
                className="w-28 rounded-md border border-slate-300 px-2 py-1 text-sm"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            ) : (
              <div className="font-medium">
                {quote.selling_price ?? "—"} {quote.currency}
              </div>
            )}
          </div>
          <div>
            <div className="text-xs uppercase text-slate-500">Gross margin</div>
            <div className="font-medium">{quote.gross_margin ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-500">Margin %</div>
            <div className="font-medium">{quote.gross_margin_percentage ?? "—"}%</div>
          </div>
        </div>
        {pending && (
          <p className="mt-3 text-xs text-amber-700">
            Pricing requires your approval. Edit the price or text, then approve.
          </p>
        )}
      </Panel>

      <Panel
        title="Quotation text"
        actions={<CopyButton text={text} />}
      >
        <TextArea value={text} onChange={pending ? setText : undefined} rows={14} />
      </Panel>

      {pending ? (
        <Panel title="Decision">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={markSent} onChange={(e) => setMarkSent(e.target.checked)} />
              Mark as sent (schedules a follow-up)
            </label>
            <Button onClick={() => decide(true)} disabled={busy === "approve"}>
              {busy === "approve" ? "Saving…" : "Approve"}
            </Button>
            <div className="flex items-center gap-2">
              <input
                className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                placeholder="Lost reason (optional)"
                value={lostReason}
                onChange={(e) => setLostReason(e.target.value)}
              />
              <Button variant="danger" onClick={() => decide(false)} disabled={busy === "reject"}>
                Reject
              </Button>
            </div>
          </div>
        </Panel>
      ) : (
        <Button variant="secondary" onClick={downloadPdf}>
          Download PDF
        </Button>
      )}
    </div>
  );
}

export default function QuotePage({ params }: { params: { id: string } }) {
  return (
    <RequireAuth>
      <QuoteDetail id={Number(params.id)} />
    </RequireAuth>
  );
}
