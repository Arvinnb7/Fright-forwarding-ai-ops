"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  AuditEvent,
  Customer,
  LaneRateMemory,
  Member,
  PartnerRate,
  RateAnalysis,
  RFQ,
  PARTNER_TYPES,
  RFQ_STATUSES,
} from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, CopyButton, ErrorText, Field, Panel, TextArea } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

function Detail({ id }: { id: number }) {
  const router = useRouter();
  const [rfq, setRfq] = useState<RFQ | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [error, setError] = useState("");

  // editable fields
  const [edit, setEdit] = useState<Partial<RFQ>>({});

  // drafts
  const [missingDraft, setMissingDraft] = useState("");
  const [partnerType, setPartnerType] = useState(PARTNER_TYPES[0]);
  const [rateDraft, setRateDraft] = useState("");
  const [busy, setBusy] = useState("");

  // rates
  const [rates, setRates] = useState<PartnerRate[]>([]);
  const [analysis, setAnalysis] = useState<RateAnalysis | null>(null);
  const [newRate, setNewRate] = useState({
    partner_name: "",
    partner_type: PARTNER_TYPES[0],
    cost_amount: "",
    currency: "USD",
    transit_time: "",
  });

  // quote
  const [markup, setMarkup] = useState("20");
  const [selectedRate, setSelectedRate] = useState<number | "">("");
  // rate memory (prior rates on this lane)
  const [memory, setMemory] = useState<LaneRateMemory | null>(null);
  const [reusing, setReusing] = useState<number | null>(null);
  // team + trail
  const [members, setMembers] = useState<Member[]>([]);
  const [activity, setActivity] = useState<AuditEvent[]>([]);

  function loadRfq() {
    api.get<RFQ>(`/api/rfqs/${id}`).then((r) => {
      setRfq(r);
      setEdit({
        origin: r.origin ?? "",
        destination: r.destination ?? "",
        commodity: r.commodity ?? "",
        incoterm: r.incoterm ?? "",
        hs_code: r.hs_code ?? "",
        gross_weight: r.gross_weight ?? "",
        container_type: r.container_type ?? "",
        status: r.status,
      });
    });
  }
  function loadRates() {
    api.get<PartnerRate[]>(`/api/rfqs/${id}/rates`).then(setRates).catch(() => {});
  }
  function loadActivity() {
    api
      .get<AuditEvent[]>(`/api/audit?entity_type=RFQ&entity_id=${id}&limit=15`)
      .then(setActivity)
      .catch(() => setActivity([]));
  }
  function loadMemory() {
    api
      .get<LaneRateMemory>(`/api/rfqs/${id}/rate-suggestions`)
      .then(setMemory)
      .catch(() => setMemory(null));
  }
  useEffect(() => {
    loadRfq();
    loadRates();
    loadMemory();
    api.get<Customer[]>("/api/customers").then(setCustomers).catch(() => {});
    api.get<Member[]>("/api/auth/users").then(setMembers).catch(() => {});
    loadActivity();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function assignOwner(ownerId: string) {
    await api.patch(`/api/rfqs/${id}`, {
      owner_id: ownerId ? Number(ownerId) : null,
    });
    loadRfq();
    loadActivity();
  }

  async function assignCustomer(customerId: string) {
    await api.patch(`/api/rfqs/${id}`, {
      customer_id: customerId ? Number(customerId) : null,
    });
    loadRfq();
  }

  async function saveFields() {
    setError("");
    try {
      await api.patch(`/api/rfqs/${id}`, edit);
      loadRfq();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function gen(kind: "missing" | "rate") {
    setBusy(kind);
    setError("");
    try {
      if (kind === "missing") {
        const r = await api.post<{ draft: string }>(`/api/rfqs/${id}/missing-info-draft`);
        setMissingDraft(r.draft);
      } else {
        const r = await api.post<{ draft: string }>(`/api/rfqs/${id}/rate-request-draft`, {
          partner_type: partnerType,
        });
        setRateDraft(r.draft);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function addRate() {
    try {
      await api.post(`/api/rfqs/${id}/rates`, {
        ...newRate,
        cost_amount: newRate.cost_amount ? Number(newRate.cost_amount) : null,
      });
      setNewRate({ ...newRate, partner_name: "", cost_amount: "", transit_time: "" });
      loadRates();
      loadMemory();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  /** Copy a remembered rate onto this RFQ and pre-select it, so the next click
   *  is "Start quote" rather than another form. */
  async function useRemembered(rateId: number) {
    setReusing(rateId);
    setError("");
    try {
      const copied = await api.post<PartnerRate>(
        `/api/rfqs/${id}/rates/from-history/${rateId}`
      );
      loadRates();
      loadMemory();
      setSelectedRate(copied.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReusing(null);
    }
  }

  async function analyze() {
    setBusy("analyze");
    setError("");
    try {
      const a = await api.post<RateAnalysis>(`/api/rfqs/${id}/rates/analyze`);
      setAnalysis(a);
      if (a.recommended_rate_id) setSelectedRate(a.recommended_rate_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function startQuote() {
    setBusy("quote");
    setError("");
    try {
      const review = await api.post<{ quote_id: number }>(`/api/quotes/start`, {
        rfq_id: id,
        selected_rate_id: selectedRate === "" ? null : selectedRate,
        markup_value: Number(markup),
      });
      router.push(`/quotes/${review.quote_id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  if (!rfq) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            {rfq.reference ?? `RFQ #${rfq.id}`}
          </h1>
          <p className="text-sm text-slate-500">
            {rfq.origin ?? "?"} → {rfq.destination ?? "?"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={rfq.customer_id ?? ""}
            onChange={(e) => assignCustomer(e.target.value)}
          >
            <option value="">— No customer —</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>{c.company_name}</option>
            ))}
          </select>
          <select
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={rfq.owner_id ?? ""}
            onChange={(e) => assignOwner(e.target.value)}
            title="Who is handling this enquiry"
          >
            <option value="">— Unassigned —</option>
            {members.map((m) => (
              <option key={m.id} value={m.id}>{m.full_name ?? m.email}</option>
            ))}
          </select>
          <StatusBadge value={rfq.status} />
        </div>
      </div>

      <ErrorText>{error}</ErrorText>

      <Panel title="Shipment details" actions={<Button onClick={saveFields}>Save</Button>}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Origin" value={edit.origin ?? ""} onChange={(v) => setEdit({ ...edit, origin: v })} />
          <Field label="Destination" value={edit.destination ?? ""} onChange={(v) => setEdit({ ...edit, destination: v })} />
          <Field label="Container" value={edit.container_type ?? ""} onChange={(v) => setEdit({ ...edit, container_type: v })} />
          <Field label="Commodity" value={edit.commodity ?? ""} onChange={(v) => setEdit({ ...edit, commodity: v })} />
          <Field label="HS code" value={edit.hs_code ?? ""} onChange={(v) => setEdit({ ...edit, hs_code: v })} />
          <Field label="Gross weight" value={edit.gross_weight ?? ""} onChange={(v) => setEdit({ ...edit, gross_weight: v })} />
          <Field label="Incoterm" value={edit.incoterm ?? ""} onChange={(v) => setEdit({ ...edit, incoterm: v })} />
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">Status</span>
            <select
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={edit.status ?? ""}
              onChange={(e) => setEdit({ ...edit, status: e.target.value })}
            >
              {RFQ_STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
        {rfq.missing_fields.length > 0 && (
          <div className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Missing: {rfq.missing_fields.join(", ")}
          </div>
        )}
        {rfq.recommended_next_action && (
          <p className="mt-2 text-sm text-slate-500">Next: {rfq.recommended_next_action}</p>
        )}
      </Panel>

      <Panel
        title="Missing-information email (draft)"
        actions={
          <Button variant="secondary" onClick={() => gen("missing")} disabled={busy === "missing"}>
            {busy === "missing" ? "Drafting…" : "Generate draft"}
          </Button>
        }
      >
        {missingDraft ? (
          <div className="space-y-2">
            <TextArea value={missingDraft} onChange={setMissingDraft} />
            <CopyButton text={missingDraft} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            Generate a professional email asking the customer for the missing details.
          </p>
        )}
      </Panel>

      <Panel
        title="Partner rate-request (draft)"
        actions={
          <div className="flex gap-2">
            <select
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={partnerType}
              onChange={(e) => setPartnerType(e.target.value)}
            >
              {PARTNER_TYPES.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
            <Button variant="secondary" onClick={() => gen("rate")} disabled={busy === "rate"}>
              {busy === "rate" ? "Drafting…" : "Generate"}
            </Button>
          </div>
        }
      >
        {rateDraft ? (
          <div className="space-y-2">
            <TextArea value={rateDraft} onChange={setRateDraft} />
            <CopyButton text={rateDraft} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            Generate a rate-request message tailored to the selected partner type.
          </p>
        )}
      </Panel>

      {memory && memory.lane_known && memory.suggestions.length > 0 && (
        <Panel
          title="Rate memory — this lane has been priced before"
          actions={
            <span className="text-xs text-slate-500">
              {memory.exact_matches} exact
              {memory.route_matches > 0 && `, ${memory.route_matches} same route`}
              {memory.median_cost != null && ` · median ${memory.median_cost}`}
            </span>
          }
        >
          <p className="mb-3 text-sm text-slate-500">
            Use one of these to answer now instead of waiting for a partner
            reply. Nothing is applied automatically — the copy is yours to edit,
            and you should confirm it is still valid before quoting.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Partner</th>
                <th>Cost</th>
                <th>Transit</th>
                <th>Age</th>
                <th>Last quoted</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {memory.suggestions.map((s) => (
                <tr key={s.rate_id} className="border-t border-slate-100">
                  <td className="py-2">
                    <div className="font-medium text-slate-800">{s.partner_name}</div>
                    <div className="text-xs text-slate-400">
                      {s.match === "exact" ? s.source : `Same route · ${s.lane}`}
                    </div>
                  </td>
                  <td className="text-slate-700">
                    {s.cost_amount != null ? `${s.cost_amount} ${s.currency}` : "—"}
                  </td>
                  <td className="text-slate-600">{s.transit_time ?? "—"}</td>
                  <td className="text-slate-500">
                    {s.age_days}d
                    {s.is_expired && (
                      <span className="ml-1 rounded bg-amber-100 px-1 text-xs text-amber-800">
                        expired
                      </span>
                    )}
                  </td>
                  <td className="text-slate-600">
                    {s.quoted_selling_price != null
                      ? `${s.quoted_selling_price}${s.outcome ? ` · ${s.outcome}` : ""}`
                      : "—"}
                  </td>
                  <td className="text-right">
                    <Button
                      variant="secondary"
                      onClick={() => useRemembered(s.rate_id)}
                      disabled={reusing === s.rate_id}
                    >
                      {reusing === s.rate_id ? "Adding…" : "Use"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      <Panel title="Partner rates">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-6">
          <input className="rounded-md border border-slate-300 px-2 py-1 text-sm sm:col-span-2" placeholder="Partner name" value={newRate.partner_name} onChange={(e) => setNewRate({ ...newRate, partner_name: e.target.value })} />
          <select className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={newRate.partner_type} onChange={(e) => setNewRate({ ...newRate, partner_type: e.target.value })}>
            {PARTNER_TYPES.map((p) => (<option key={p}>{p}</option>))}
          </select>
          <input className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Cost" value={newRate.cost_amount} onChange={(e) => setNewRate({ ...newRate, cost_amount: e.target.value })} />
          <input className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Transit" value={newRate.transit_time} onChange={(e) => setNewRate({ ...newRate, transit_time: e.target.value })} />
          <Button onClick={addRate} disabled={!newRate.partner_name}>Add</Button>
        </div>

        {rates.length > 0 && (
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Pick</th>
                <th>Partner</th>
                <th>Cost</th>
                <th>Transit</th>
              </tr>
            </thead>
            <tbody>
              {rates.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="py-2">
                    <input type="radio" name="rate" checked={selectedRate === r.id} onChange={() => setSelectedRate(r.id)} />
                  </td>
                  <td>{r.partner_name}</td>
                  <td>{r.cost_amount != null ? `${r.cost_amount} ${r.currency}` : "—"}</td>
                  <td>{r.transit_time ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {rates.length >= 1 && (
          <div className="mt-3">
            <Button variant="secondary" onClick={analyze} disabled={busy === "analyze"}>
              {busy === "analyze" ? "Analyzing…" : "Compare rates (AI)"}
            </Button>
          </div>
        )}

        {analysis && (
          <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm">
            <p className="font-medium text-slate-800">
              Recommended: rate #{analysis.recommended_rate_id ?? "—"}
            </p>
            {analysis.recommendation_reason && (
              <p className="text-slate-600">{analysis.recommendation_reason}</p>
            )}
            {analysis.tradeoffs && (
              <p className="mt-1 text-slate-500">{analysis.tradeoffs}</p>
            )}
            <ul className="mt-2 space-y-1">
              {analysis.options.map((o) => (
                <li key={o.rate_id} className="text-slate-600">
                  <span className="font-medium">{o.partner_name}:</span> {o.summary}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Panel>

      <Panel
        title="Build quotation"
        actions={
          <Button onClick={startQuote} disabled={busy === "quote"}>
            {busy === "quote" ? "Building…" : "Start quote →"}
          </Button>
        }
      >
        <div className="flex items-end gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">Markup %</span>
            <input className="w-28 rounded-md border border-slate-300 px-3 py-2 text-sm" value={markup} onChange={(e) => setMarkup(e.target.value)} />
          </label>
          <p className="text-sm text-slate-500">
            Uses the selected rate above (or its cost). You approve the price on the next step.
          </p>
        </div>
      </Panel>

      {activity.length > 0 && (
        <Panel title="Activity">
          <ul className="space-y-2 text-sm">
            {activity.map((event) => (
              <li key={event.id} className="flex justify-between gap-4">
                <span className="text-slate-700">{event.summary}</span>
                <span className="shrink-0 text-xs text-slate-400">
                  {event.actor} · {new Date(event.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

export default function RFQDetailPage({ params }: { params: { id: string } }) {
  return (
    <RequireAuth>
      <Detail id={Number(params.id)} />
    </RequireAuth>
  );
}
