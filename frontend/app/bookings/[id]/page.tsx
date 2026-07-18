"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Booking,
  BOOKING_STATUSES,
  DOCUMENT_STATUSES,
  Issue,
  ShipmentDocument,
} from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, CopyButton, ErrorText, Field, Panel, TextArea } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

function BookingDetail({ id }: { id: number }) {
  const [booking, setBooking] = useState<Booking | null>(null);
  const [docs, setDocs] = useState<ShipmentDocument[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [edit, setEdit] = useState<Partial<Booking>>({});
  const [newDoc, setNewDoc] = useState("");
  const [updateDraft, setUpdateDraft] = useState("");
  const [extraNote, setExtraNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  function load() {
    api.get<Booking>(`/api/bookings/${id}`).then((b) => {
      setBooking(b);
      setEdit({
        shipper: b.shipper ?? "",
        consignee: b.consignee ?? "",
        notify_party: b.notify_party ?? "",
        assigned_to: b.assigned_to ?? "",
        status: b.status,
        etd: b.etd ?? "",
        eta: b.eta ?? "",
      });
    });
    api.get<ShipmentDocument[]>(`/api/bookings/${id}/documents`).then(setDocs).catch(() => {});
    api.get<Issue[]>("/api/issues").then((all) =>
      setIssues(all.filter((i) => i.booking_id === id))
    ).catch(() => {});
  }
  useEffect(load, [id]);

  async function save() {
    setBusy("save");
    setError("");
    try {
      const payload = { ...edit, etd: edit.etd || null, eta: edit.eta || null };
      await api.patch(`/api/bookings/${id}`, payload);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function suggestDocs() {
    setBusy("suggest");
    setError("");
    try {
      await api.post(`/api/bookings/${id}/documents/suggest?create=true`);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function addDoc() {
    if (!newDoc.trim()) return;
    await api.post(`/api/bookings/${id}/documents`, { document_type: newDoc });
    setNewDoc("");
    load();
  }

  async function setDocStatus(docId: number, status: string) {
    await api.patch(`/api/bookings/documents/${docId}`, { status });
    load();
  }

  async function genUpdate() {
    setBusy("update");
    setError("");
    try {
      const r = await api.post<{ draft: string }>(`/api/bookings/${id}/status-update-draft`, {
        extra_note: extraNote || null,
      });
      setUpdateDraft(r.draft);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  if (!booking) return <p className="text-sm text-slate-500">Loading…</p>;

  const money = (v: number | null) =>
    v == null ? "—" : `${v.toLocaleString()} ${booking.currency}`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            {booking.job_number ?? `Booking #${booking.id}`}
          </h1>
          <p className="text-sm text-slate-500">
            {booking.origin ?? "?"} → {booking.destination ?? "?"} ·{" "}
            {booking.cargo_details ?? "cargo n/a"}
          </p>
        </div>
        <StatusBadge value={booking.status} />
      </div>
      <ErrorText>{error}</ErrorText>

      <Panel title="Commercials">
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs uppercase text-slate-500">Agreed price</div>
            <div className="font-medium">{money(booking.agreed_price)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-500">Estimated cost</div>
            <div className="font-medium">{money(booking.estimated_cost)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-500">Expected margin</div>
            <div className="font-medium">{money(booking.estimated_margin)}</div>
          </div>
        </div>
      </Panel>

      <Panel title="Job details" actions={<Button onClick={save} disabled={busy === "save"}>Save</Button>}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Shipper" value={(edit.shipper as string) ?? ""} onChange={(v) => setEdit({ ...edit, shipper: v })} />
          <Field label="Consignee" value={(edit.consignee as string) ?? ""} onChange={(v) => setEdit({ ...edit, consignee: v })} />
          <Field label="Notify party" value={(edit.notify_party as string) ?? ""} onChange={(v) => setEdit({ ...edit, notify_party: v })} />
          <Field label="Assigned to" value={(edit.assigned_to as string) ?? ""} onChange={(v) => setEdit({ ...edit, assigned_to: v })} />
          <Field label="ETD (YYYY-MM-DD)" value={(edit.etd as string) ?? ""} onChange={(v) => setEdit({ ...edit, etd: v })} />
          <Field label="ETA (YYYY-MM-DD)" value={(edit.eta as string) ?? ""} onChange={(v) => setEdit({ ...edit, eta: v })} />
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">Status</span>
            <select
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={(edit.status as string) ?? ""}
              onChange={(e) => setEdit({ ...edit, status: e.target.value })}
            >
              {BOOKING_STATUSES.map((s) => (<option key={s}>{s}</option>))}
            </select>
          </label>
        </div>
      </Panel>

      <Panel
        title="Document checklist"
        actions={
          <Button variant="secondary" onClick={suggestDocs} disabled={busy === "suggest"}>
            {busy === "suggest" ? "Suggesting…" : "AI suggest documents"}
          </Button>
        }
      >
        <div className="mb-3 flex gap-2">
          <input
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            placeholder="Add document type (e.g. Commercial Invoice)"
            value={newDoc}
            onChange={(e) => setNewDoc(e.target.value)}
          />
          <Button onClick={addDoc} disabled={!newDoc.trim()}>Add</Button>
        </div>
        {docs.length === 0 ? (
          <p className="text-sm text-slate-500">No documents tracked yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Document</th>
                <th>Status</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-t border-slate-100">
                  <td className="py-2 font-medium text-slate-800">{d.document_type}</td>
                  <td>
                    <select
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                      value={d.status}
                      onChange={(e) => setDocStatus(d.id, e.target.value)}
                    >
                      {DOCUMENT_STATUSES.map((s) => (<option key={s}>{s}</option>))}
                    </select>
                  </td>
                  <td className="text-slate-500">{d.notes ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel
        title="Customer status update (draft)"
        actions={
          <Button variant="secondary" onClick={genUpdate} disabled={busy === "update"}>
            {busy === "update" ? "Drafting…" : "Generate draft"}
          </Button>
        }
      >
        <input
          className="mb-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder="Optional extra note (e.g. delay reason)"
          value={extraNote}
          onChange={(e) => setExtraNote(e.target.value)}
        />
        {updateDraft ? (
          <div className="space-y-2">
            <TextArea value={updateDraft} onChange={setUpdateDraft} rows={9} />
            <CopyButton text={updateDraft} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            Generates a professional update based on the current status ({booking.status}).
          </p>
        )}
      </Panel>

      {issues.length > 0 && (
        <Panel title="Issues on this shipment">
          <ul className="space-y-1 text-sm">
            {issues.map((i) => (
              <li key={i.id} className="flex items-center gap-2">
                <StatusBadge value={i.severity} />
                <span className="font-medium">{i.issue_type}</span>
                <span className="text-slate-500">{i.description}</span>
                <StatusBadge value={i.status} />
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

export default function BookingPage({ params }: { params: { id: string } }) {
  return (
    <RequireAuth>
      <BookingDetail id={Number(params.id)} />
    </RequireAuth>
  );
}
